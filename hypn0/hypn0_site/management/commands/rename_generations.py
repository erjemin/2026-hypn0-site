import re
from typing import Optional

from django.core.management.base import BaseCommand
from django.db import transaction

from hypn0_site.models import TbHypn0Item
from hypn0_site.services.naming import generate_hypno_title


class Command(BaseCommand):
    """
    Массовое переименование названий генераций (TbHypn0Item.s_title) на английский язык.

    АРХИТЕКТУРНОЕ НАЗНАЧЕНИЕ:
    =========================
    1. Локализация каталога и прод-базы:
       Переводит существующие русскоязычные названия картин в базе данных
       на сочные англоязычные гипнотические тайтлы в стиле Гипножабы.

    2. Детерминированность vs Случайность:
       По умолчанию использует детерминированный сид на базе ID генерации (item.id + seed_offset),
       что обеспечивает стабильность результатов при повторных запусках (идемпотентность).
       Флаг --random позволяет генерировать полностью случайные тайтлы.

    3. Безопасность и оптимизация:
       - Пакетное обновление через bulk_update порциями (--batch-size).
       - Режим предварительного просмотра (--dry-run).
       - Фильтрация по умолчанию только кириллических / пустых названий (или всех с флагом --all).
    """

    help = "Массовое переименование названий генераций на английский язык"

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Тестовый прогон: показать изменения без сохранения в базу данных",
        )
        parser.add_argument(
            "--all",
            action="store_true",
            help="Переименовать абсолютно все генерации (по умолчанию только с кириллицей или пустые)",
        )
        parser.add_argument(
            "--only-cyrillic",
            action="store_true",
            help="Переименовывать только записи с кириллическими символами в названии (включено по умолчанию)",
        )
        parser.add_argument(
            "--batch-size",
            type=int,
            default=500,
            help="Размер пакета для bulk_update (по умолчанию: 500)",
        )
        parser.add_argument(
            "--limit",
            type=int,
            default=None,
            help="Ограничить количество обрабатываемых записей",
        )
        parser.add_argument(
            "--seed-offset",
            type=int,
            default=0,
            help="Смещение для детерминированного генератора сидов (по умолчанию: 0)",
        )
        parser.add_argument(
            "--random",
            action="store_true",
            help="Использовать недетерминированные случайные сиды вместо ID записи",
        )

    def handle(self, *args, **options):
        dry_run: bool = options["dry_run"]
        rename_all: bool = options["all"]
        batch_size: int = options["batch_size"]
        limit: Optional[int] = options["limit"]
        seed_offset: int = options["seed_offset"]
        use_random: bool = options["random"]

        self.stdout.write(
            self.style.NOTICE(
                f"Старт процесса переименования генераций "
                f"(dry_run={dry_run}, rename_all={rename_all}, batch_size={batch_size}, random={use_random})..."
            )
        )

        cyrillic_pattern = re.compile(r"[а-яА-ЯёЁ]")

        qs = TbHypn0Item.objects.all().only("id", "s_title").order_by("id")
        total_in_db = qs.count()

        if total_in_db == 0:
            self.stdout.write(self.style.WARNING("В базе данных нет генераций для обработки."))
            return

        to_update = []
        renamed_count = 0
        preview_samples = []

        for item in qs.iterator(chunk_size=batch_size):
            old_title = item.s_title or ""

            # Проверяем критерий необходимости переименования
            needs_rename = False
            if rename_all:
                needs_rename = True
            else:
                # По умолчанию: кириллица или пустой заголовок
                if not old_title.strip() or cyrillic_pattern.search(old_title):
                    needs_rename = True

            if not needs_rename:
                continue

            # Генерация нового англоязычного тайтла
            seed = None if use_random else (item.id + seed_offset)
            new_title = generate_hypno_title(seed=seed)

            if len(preview_samples) < 15:
                preview_samples.append((item.id, old_title, new_title))

            item.s_title = new_title
            to_update.append(item)
            renamed_count += 1

            if limit is not None and renamed_count >= limit:
                break

            # Пакетное сохранение порциями
            if not dry_run and len(to_update) >= batch_size:
                with transaction.atomic():
                    TbHypn0Item.objects.bulk_update(to_update, fields=["s_title"])
                to_update.clear()

        # Сохранение остатка
        if not dry_run and to_update:
            with transaction.atomic():
                TbHypn0Item.objects.bulk_update(to_update, fields=["s_title"])
            to_update.clear()

        # Вывод примеров переименования
        if preview_samples:
            self.stdout.write("\nПримеры переименований (первые до 15 записей):")
            self.stdout.write("-" * 70)
            for item_id, old_t, new_t in preview_samples:
                self.stdout.write(f" [ID {item_id:5d}] «{old_t}» -> «{new_t}»")
            self.stdout.write("-" * 70)

        self.stdout.write(f"\nВсего записей в базе данных: {total_in_db}")
        self.stdout.write(f"Отобрано для переименования: {renamed_count}")

        if dry_run:
            self.stdout.write(
                self.style.WARNING(
                    f"\n[DRY RUN] Проверено {renamed_count} записей. Изменения НЕ сохранены в БД. "
                    "Запустите без флага --dry-run для применения."
                )
            )
        else:
            self.stdout.write(
                self.style.SUCCESS(f"\nУспешно переименовано {renamed_count} генераций в базе данных!")
            )
