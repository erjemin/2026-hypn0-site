import math
from datetime import timedelta
from django.core.management.base import BaseCommand
from django.utils import timezone
from django.conf import settings
from django.db.models import Count, Q

from hypn0_site.models import TbHypn0Item, TbVote


class Command(BaseCommand):
    """
    Пакетный пересчет рейтинга популярности (f_score) и выявление аномалий (накрутка / шейминг).

    АРХИТЕКТУРНЫЕ ПРИНЦИПЫ СКОРИНГА HYPN0:
    ======================================
    1. Изолированный атомарный скоринг бесполезен:
       Оценивать одну картину в вакууме нельзя, так как система не видит контекста:
       динамики платформы, скорости притока голосов и фонового шума.

    2. Рейтинг f_score нужен для Smart Retention (умной очистки диска):
       Он определяет, какие файлы удалять первыми при превышении дисковой квоты,
       а какие оставлять как ценные экспонаты.

    3. Разделение UI-счетчиков и весов скоринга:
       Поля `i_likes_count` и `i_claims_count` в TbHypn0Item используются для быстрого рендера в UI.
       Истинные веса (+1 лайк, +2 автор, -2 жалоба) + штампы-времени и sha256 от фингер-принтами браузеров хранятся в TbVote.

    4. Учет "старения" голосов (Time-Decay) (алгоритм, возможно, будет пересмотрен):
       Свежий лайк имеет полный вес, а старый голос плавно затухает по экспоненциальному закону:
       Weight(t) = BaseWeight * 2^(-dt / HalfLife).

    5. "Средняя температура по больнице" и Коридоры аномалий (алгоритм, возможно, будет пересмотрен:
       Перед расчетом анализируется средняя скорость голосования по всей платформе за окно (например, 24ч).
       - Спайк лайков (> N раз выше нормы): подозрение на накрутку (Level.SUSPICIOUS).
       - Спайк клеймов (> N% от голосов за короткий промежуток): скоординированный шейминг (Level.SHAMED).
       - Стабильный интерес: прогретая картина переходит в Level.LEVEL_1 (ожидает модерации).

    6. Базовая формула гравитации с логарифмическим сглаживанием:
       Score = (ln(1 + max(0, WeightedVotes)) + Bonus_level) / ((Age_in_hours + 2) ^ GAMMA)
    """

    help = "Пакетный пересчет рейтинга популярности f_score и выявление аномалий в голосах"

    def add_arguments(self, parser):
        parser.add_argument(
            "--gamma",
            type=float,
            default=getattr(settings, "GAMMA", 1.5),
            help="Коэффициент гравитации затухания картины по времени (по умолчанию: 1.5)",
        )
        parser.add_argument(
            "--half-life-days",
            type=float,
            default=14.0,
            help="Период полураспада веса отдельного голоса в днях (по умолчанию: 14 дней)",
        )
        parser.add_argument(
            "--spike-multiplier",
            type=float,
            default=4.0,
            help="Во сколько раз скорость лайков должна превышать среднюю для детекции накрутки (по умолчанию: 4.0)",
        )
        parser.add_argument(
            "--shame-claim-ratio",
            type=float,
            default=0.35,
            help="Доля жалоб среди свежих голосов для детекции шейминга (по умолчанию: 0.35 или 35%)",
        )
        parser.add_argument(
            "--warmup-votes-threshold",
            type=int,
            default=10,
            help="Минимальное число взвешенных голосов для перехода CANDIDATE -> LEVEL_1 (по умолчанию: 10)",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Тестовый прогон: выполнить все расчеты без записи изменений в БД",
        )

    def handle(self, *args, **options):
        gamma = options["gamma"]
        half_life_days = options["half_life_days"]
        spike_multiplier = options["spike_multiplier"]
        shame_claim_ratio = options["shame_claim_ratio"]
        warmup_threshold = options["warmup_votes_threshold"]
        dry_run = options["dry_run"]

        now = timezone.now()
        self.stdout.write(self.style.NOTICE(f"[{now.strftime('%Y-%m-%d %H:%M:%S')}] Старт скоринга Hypn0..."))

        # -----------------------------------------------------------------------------------------
        # ШАГ 1: Определение "средней температуры по больнице" за последние 24 часа
        # -----------------------------------------------------------------------------------------
        recent_window = now - timedelta(hours=24)
        recent_votes_qs = TbVote.objects.filter(d_created_at__gte=recent_window)
        total_recent_votes = recent_votes_qs.count()

        active_items_count = TbHypn0Item.objects.filter(
            d_created_at__gte=now - timedelta(days=30)
        ).count() or 1

        # Среднее число голосов на одну активную картину за сутки
        avg_votes_per_item_24h = total_recent_votes / active_items_count
        self.stdout.write(
            f"Базовые метрики за 24ч: голосов всего={total_recent_votes}, "
            f"активных картин={active_items_count}, среднее={avg_votes_per_item_24h:.2f} голосов/картину"
        )

        # -----------------------------------------------------------------------------------------
        # ШАГ 2: Выборка картин для пересчета
        # Бессмертные картины (Level.IMMORTAL) не требуют скоринга для очистки, но могут участвовать
        # -----------------------------------------------------------------------------------------
        items = TbHypn0Item.objects.exclude(i_level=TbHypn0Item.Level.IMMORTAL).prefetch_related("votes")
        total_items = items.count()

        if total_items == 0:
            self.stdout.write(self.style.WARNING("В базе данных пока нет картин для пересчета."))
            return

        updated_count = 0
        decay_lambda = math.log(2) / (half_life_days * 24.0)  # константа затухания в час

        for item in items:
            # 1. Считаем взвешенные голоса с учетом возраста каждого голоса
            item_votes = list(item.votes.all())
            weighted_likes = 0.0
            recent_likes_24h = 0
            recent_claims_24h = 0

            for v in item_votes:
                vote_age_hours = max(0.0, (now - v.d_created_at).total_seconds() / 3600.0)
                # Экспоненциальное затухание веса: e^(-lambda * dt)
                decay_factor = math.exp(-decay_lambda * vote_age_hours)
                weighted_likes += v.i_direction * decay_factor

                if v.d_created_at >= recent_window:
                    if v.i_direction in (TbVote.Direction.LIKE, TbVote.Direction.AUTHOR):
                        recent_likes_24h += 1
                    elif v.i_direction == TbVote.Direction.CLAIM:
                        recent_claims_24h += 1

            # 2. Детекция аномалий (шейминг vs спайк накрутки)
            new_level = item.i_level
            recent_total_24h = recent_likes_24h + recent_claims_24h

            if recent_total_24h >= 5:
                # Проверка на шейминг (резкий наплыв жалоб)
                claim_ratio = recent_claims_24h / recent_total_24h
                if claim_ratio >= shame_claim_ratio:
                    new_level = TbHypn0Item.Level.SHAMED
                    self.stdout.write(
                        self.style.WARNING(f"Аномалия [SHAMED]: Картина {item.s_hash_id} доля жалоб={claim_ratio:.1%}")
                    )

                # Проверка на спайк лайков (накрутка)
                elif avg_votes_per_item_24h > 0 and recent_likes_24h > (avg_votes_per_item_24h * spike_multiplier) and recent_likes_24h >= 20:
                    new_level = TbHypn0Item.Level.SUSPICIOUS
                    self.stdout.write(
                        self.style.WARNING(f"Аномалия [SUSPICIOUS]: Картина {item.s_hash_id} лайков за 24ч={recent_likes_24h}")
                    )

            # Проверка перехода CANDIDATE -> LEVEL_1 (Прогрета, набрала массу)
            if item.i_level == TbHypn0Item.Level.CANDIDATE and weighted_likes >= warmup_threshold and new_level == item.i_level:
                new_level = TbHypn0Item.Level.LEVEL_1
                self.stdout.write(
                    self.style.SUCCESS(f"Прогрев [CANDIDATE -> LEVEL_1]: Картина {item.s_hash_id} набрала вес={weighted_likes:.1f}")
                )

            # 3. Расчет нового f_score (Гравитационная модель + логарифм)
            item_age_hours = max(0.0, (now - item.d_created_at).total_seconds() / 3600.0)

            # Бонус от модераторского уровня
            level_bonus = 0.0
            if item.i_level == TbHypn0Item.Level.LEVEL_1:
                level_bonus = 1.5
            elif item.i_level == TbHypn0Item.Level.LEVEL_2:
                level_bonus = 4.0

            if weighted_likes <= 0:
                raw_score = weighted_likes  # Отрицательный или нулевой скор
            else:
                raw_score = (math.log(1.0 + weighted_likes) + level_bonus) / ((item_age_hours + 2.0) ** gamma)

            # 4. Инерционное сглаживание со старым значением (EMA) для исключения скачков
            if item.f_score != 0.0:
                alpha = 0.7  # 70% новый расчет, 30% старый инерционный рейтинг
                final_score = alpha * raw_score + (1.0 - alpha) * item.f_score
            else:
                final_score = raw_score

            # 5. Сохранение результатов
            if not dry_run:
                item.f_score = round(final_score, 6)
                if new_level != item.i_level:
                    item.i_level = new_level
                    item.save(update_fields=["f_score", "i_level", "d_updated_at"])
                else:
                    item.save(update_fields=["f_score", "d_updated_at"])

            updated_count += 1

        status_msg = "ПРОБНЫЙ ПРОГОН (DRY RUN)" if dry_run else "УСПЕШНО ОБНОВЛЕНО"
        self.stdout.write(
            self.style.SUCCESS(f"[{status_msg}] Обработано картин: {updated_count}/{total_items}")
        )
