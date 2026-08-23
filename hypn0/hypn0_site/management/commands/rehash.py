from django.core.management.base import BaseCommand
from django.conf import settings
from hashids import Hashids

from hypn0_site.models import TbHypn0Item


class Command(BaseCommand):
    """
    Проверка и синхронизация s_hash_id с текущими настройками HASHIDS_SALT.

    АРХИТЕКТУРНОЕ НАЗНАЧЕНИЕ:
    =========================
    1. Изоляция сред (Dev / Stage / Prod) и ротация секретов:
       В разных окружениях или при переносе базы данных значение HASHIDS_SALT может
       отличаться от исходного.

    2. Детерминированность и обратимость:
       Hashids — это однозначное обратимое кодирование: pk <-> s_hash_id.
       Если соль изменилась, старые s_hash_id в базе перестают соответствовать
       текущей конфигурации проекта.

    3. Назначение команды:
       - Сверяет каждый s_hash_id в базе с тем, что должен генерироваться при текущем settings.HASHIDS_SALT.
       - Выявляет битые, пустые или сгенерированные со старой солью идентификаторы.
       - Безопасно обновляет s_hash_id без изменения первичных ключей (pk) и других полей картины.
    """

    help = "Проверка целостности и перегенерация s_hash_id картин под текущий HASHIDS_SALT"

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Тестовый прогон: только проверить несоответствия без записи изменений в БД",
        )
        parser.add_argument(
            "--batch-size",
            type=int,
            default=500,
            help="Размер пакета для пакетного обновления (по умолчанию: 500)",
        )

    def handle(self, *args, **options):
        dry_run = options["dry_run"]
        batch_size = options["batch_size"]

        salt = getattr(settings, "HASHIDS_SALT", "hypn0_default_salt")
        min_length = getattr(settings, "HASHIDS_MIN_LENGTH", 6)
        hasher = Hashids(salt=salt, min_length=min_length)

        self.stdout.write(self.style.NOTICE(f"Старт проверки s_hash_id (соль: '{salt[:4]}***', min_length: {min_length})..."))

        items = TbHypn0Item.objects.all().only("id", "s_hash_id")
        total_items = items.count()

        if total_items == 0:
            self.stdout.write(self.style.WARNING("В базе данных нет картин для проверки."))
            return

        to_update = []
        mismatched_count = 0
        empty_count = 0

        for item in items.iterator(chunk_size=batch_size):
            expected_hash = hasher.encode(item.id)

            if not item.s_hash_id:
                empty_count += 1
                item.s_hash_id = expected_hash
                to_update.append(item)
            elif item.s_hash_id != expected_hash:
                mismatched_count += 1
                self.stdout.write(
                    f"Несоответствие [ID={item.id}]: текущий='{item.s_hash_id}' -> ожидаемый='{expected_hash}'"
                )
                item.s_hash_id = expected_hash
                to_update.append(item)

            # Пакетное сохранение порциями
            if not dry_run and len(to_update) >= batch_size:
                TbHypn0Item.objects.bulk_update(to_update, fields=["s_hash_id"])
                to_update.clear()

        # Сохранение остатка
        if not dry_run and to_update:
            TbHypn0Item.objects.bulk_update(to_update, fields=["s_hash_id"])

        total_issues = empty_count + mismatched_count
        self.stdout.write("--------------------------------------------------")
        self.stdout.write(f"Всего проверено записей: {total_items}")
        self.stdout.write(f"Пустых s_hash_id: {empty_count}")
        self.stdout.write(f"Несоответствующих s_hash_id: {mismatched_count}")

        if total_issues == 0:
            self.stdout.write(self.style.SUCCESS("Все s_hash_id в базе идеально соответствуют текущей соли!"))
        else:
            if dry_run:
                self.stdout.write(
                    self.style.WARNING(f"[DRY RUN] Найдено {total_issues} несоответствий. Запустите без --dry-run для применения.")
                )
            else:
                self.stdout.write(
                    self.style.SUCCESS(f"Успешно обновлено {total_issues} записей под текущую конфигурацию.")
                )
