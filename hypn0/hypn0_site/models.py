import hashlib
from django.db import models, transaction, IntegrityError
from django.db.models import F
from hashids import Hashids
from hypn0.settings import *
from django.utils import timezone

class TbHypn0Item(models.Model):
    """
    Единая модель для генераций, публичных шеров и витрины галереи.

    Поля:
    • id: идентификатор записи (AutoField, 4 байта, до ~2.14 млрд)
    • s_hash_id: хэш-сумма шеринга для SVG-генерации (Hashids)
    • s_title: Заголовок (до 255 символов, разрешен HTML)
    • file_svg: SVG-файл генерации
    • i_file_size: размер файла в байтах
    • j_metadata: метаданные файла JSON (параметры алгоритма генерации)
    • i_likes_count: количество лайков
    • i_views_count: количество просмотров
    • i_claims_count: количество жалоб/претензий (клеймов)
    • f_score: оценка для стратегии хранения и умной очистки (Smart Retention)
    • i_level: уровень хранения (свежее, модерированное, защищенное от удаления)
    • is_public: доступность по внешней ссылке
    • s_promo_url: промо-ссылка спонсора/автора
    • s_promo_title: заголовок промо-ссылки или бейджа
    • i_promo_clicks: количество переходов по промо-ссылке
    • d_created_at: дата создания записи
    • d_updated_at: дата последнего обновления записи

    Методы:
    • save(): формирование s_hash_id
    • rescore(): пересчёт рейтинга f_score
    """
    class Level(models.IntegerChoices):
        CANDIDATE = LVL_CANDIDATE, 'Candidate: Шум сознания'             # Свежая генерация. Запрет на удаление до Х дней.
        LEVEL_1 = LVL_PRE_MODERATED, 'Voted: Плеск бессознательного'     # Есть "лайки", не проверено, можно удалять при низком score
        LEVEL_2 = LVL_MODERATED, 'Moderated: Одобрено Мозговым Слизнем'  # Есть "лайки", проверено, можно удалять при низком score
        IMMORTAL = LVL_LOCK_FOR_DELETION, 'Locked: Глубокий транс'       # Нельзя удалять, даже при низком score

    id = models.AutoField(
        primary_key=True,
        verbose_name="ID",
        help_text="Первичный ключ (~2.14 млрд записей, 4 байта)",
    )
    s_hash_id = models.CharField(
        max_length=16,
        unique=True,
        verbose_name="ID-Хэш",
    )
    s_title = models.CharField(
        max_length=255,
        verbose_name="Название генерации",
        help_text="Заголовок для генерации. Включена HTML-типографика. 255 символов максимум.",
    )
    file_svg = models.FileField(
        upload_to="svg/%Y/%m/",
        verbose_name="SVG-файл",
        help_text="Результирующий SVG-файл генерации",
    )
    i_file_size = models.PositiveIntegerField(
        default=0,
        verbose_name="Размер файла",
        help_text="Размер файла в байтах",
    )

    # НА ВСЯКИЙ СЛУЧАЙ: Метаданные и снимок параметров для возможного клонирования настроек
    j_metadata = models.JSONField(
        default=dict,
        blank=True,
        verbose_name="Параметры генерации",
        help_text="Метаданные и параметры для возможного клонирования настроек",
    )

    # Популярность
    i_likes_count = models.PositiveIntegerField(
        default=0,
        db_index=True,
        verbose_name="Число лайков",
        help_text="Число лайков гипнотической SVG-картины. Поле используется для отображения в интерфейсе. Для расчета"
                  " рейтинга популярности намеренно НЕ ИСПОЛЬЗУЕТСЯ. Рейтинг будет рассчитан на основе таблицы"
                  " <tt>Голоса/Лайка</tt> с учетом весов лайков и клаймов.",
    )
    i_views_count = models.PositiveIntegerField(
        default=0,
        verbose_name="Число просмотров",
    )
    i_claims_count = models.PositiveIntegerField(
        default=0,
        verbose_name="Число жалоб",
        help_text="Число жалоб на гипнотическую SVG-картину. Поле используется для отображения в интерфейсе. Для расчета"
                  " рейтинга популярности намеренно НЕ ИСПОЛЬЗУЕТСЯ. Рейтинг будет рассчитан на основе таблицы"
                  " <tt>Голоса/Лайка</tt> с учетом весов лайков и клаймов.",
    )
    f_score = models.FloatField(
        default=0.0,
        db_index=True,
        verbose_name="Рейтинг популярности",
        help_text="Рейтинг для Smart Retention и определения, что удалять при чистке по лимитам, а что оставлять",
    )

    # Модерация
    i_level = models.IntegerField(
        choices=Level.choices,
        default=Level.CANDIDATE,
        help_text="Уровень",
        verbose_name="В какой группе находится SVG-файл генерации",
    )
    is_public = models.BooleanField(
        default=True,
        help_text="Доступность по прямой ссылке",
        verbose_name="Публичный доступ",
    )

    # Промо-блок (на перспективу)
    s_promo_url = models.URLField(
        blank=True,
        default="",
        verbose_name="Промо-ссылка",
    )
    s_promo_title = models.CharField(
        max_length=100,
        blank=True,
        default="",
        verbose_name="Бейдж/автор промо",
    )
    i_promo_clicks = models.PositiveIntegerField(
        default=0,
        verbose_name="Клики по промо",
    )

    d_created_at = models.DateTimeField(
        auto_now_add=True,
        db_index=True,
        verbose_name="Дата создания",
    )
    d_updated_at = models.DateTimeField(
        auto_now=True,
        db_index=True,
        verbose_name="Дата обновления",
    )

    class Meta:
        verbose_name = "Гипно-картина"
        verbose_name_plural = "Гипно-картины"
        ordering = ["-d_created_at"]

    def __str__(self) -> str:
        return f"{self.s_title} ({self.s_hash_id})"

    def increment_views(self):
        """Безопасный инкремент просмотров"""
        TbHypn0Item.objects.filter(id=self.id).update(i_views_count=F('i_views_count') + 1)

    def vote(self, visitor_uuid_or_fp: str, direction: int = VOTE_LIKE) -> bool:
        """
        Универсальный метод учета голоса (лайк, жалоба или авторство).

        Принимает:
        - visitor_uuid_or_fp: UUIDv4 из куки hypn0_vid или готовый 64-символьный SHA256-хэш отпечатка
        - direction: направление голоса (Direction.LIKE, Direction.CLAIM, Direction.AUTHOR)

        Возвращает:
        - True: голос успешно зафиксирован и счетчик увеличен
        - False: голос уже существовал (защита от повторного голосования) или передан пустой токен
        """
        if not visitor_uuid_or_fp:
            return False

        # Если передан сырой UUID устройства, вычисляем SHA256 отпечаток
        if len(visitor_uuid_or_fp) == 64:
            fingerprint = visitor_uuid_or_fp
        else:
            fingerprint = hashlib.sha256(f"{visitor_uuid_or_fp}:{SECRET_KEY}".encode()).hexdigest()

        try:
            # В SQLite при возникновении IntegrityError текущая транзакция может перейти в состояние ошибки. Чтобы это
            # не затрагивало последующие операции с базой, try-записи изолирована в `with transaction.atomic()`
            with transaction.atomic():
                TbVote.objects.create(
                    k_item=self,
                    i_direction=direction,
                    s_fingerprint=fingerprint,
                )
        except IntegrityError:
            # Нарушение UniqueConstraint (k_item, s_fingerprint) — голос с этого устройства уже учтен
            return False

        # Атомарный инкремент нужного счетчика в зависимости от направления
        # Используем `objects.filter()` вместо `objects.get()`, так как метод .update() вызывается только у QuerySet.
        if direction in (TbVote.Direction.LIKE, TbVote.Direction.AUTHOR):
            TbHypn0Item.objects.filter(id=self.id).update(i_likes_count=F('i_likes_count') + 1)
        elif direction == TbVote.Direction.CLAIM:
            TbHypn0Item.objects.filter(id=self.id).update(i_claims_count=F('i_claims_count') + 1)

        # Рейтинг популярности f_score намеренно НЕ пересчитывается на лету при каждом лайке:
        # 1. f_score зависит от времени (возраста картины), поэтому непрерывно меняется сам по себе.
        # 2. Значение f_score необходимо только периодическому процессу умной очистки диска (Smart Retention).
        # 3. Пересчет вынесен в пакетную cron-задачу перед ротацией хранилища, что исключает лишние I/O-операции в SQLite.
        return True

    def increment_likes(self, visitor_uuid_or_fp: str) -> bool:
        """Безопасный инкремент лайков с фиксацией в TbVote"""
        return self.vote(visitor_uuid_or_fp, direction=TbVote.Direction.LIKE)

    def increment_claims(self, visitor_uuid_or_fp: str) -> bool:
        """Безопасный инкремент жалоб с фиксацией в TbVote"""
        return self.vote(visitor_uuid_or_fp, direction=TbVote.Direction.CLAIM)

    def increment_promo_clicks(self):
        """Безопасный инкремент кликов по промо"""
        TbHypn0Item.objects.filter(id=self.id).update(i_promo_clicks=F('i_promo_clicks') + 1)

    def rescore(self):
        r"""Пересчет рейтинга популярности картины
        Для оптимизации диска на сервере используется динамическая очистка на основе рейтинга популярности
        («гравитации»), а не слепой таймер:
        $$\text{Score} = \frac{\text{Likes} + \text{Bonus}_{\text{moderator}}}{(\text{Age in hours} + 2)^\gamma}$$
        """
        age_in_hours = (timezone.now() - self.d_created_at).total_seconds() / 3600 + 1
        new_score = (self.i_likes_count + self.i_level) / ((age_in_hours + 2) ** GAMMA)
        TbHypn0Item.objects.filter(id=self.id).update(f_score=new_score)

    def save(self, *args, **kwargs):
        """
        Переопределенный метод save для:
        1. Автоматического формирования s_hash_id (криптографический код)

        ЛОГИКА s_hash_id:
        - Для новых генераций: создаем код после получения ID
        - Для старых генераций БЕЗ кода: кодируем существующий ID (миграция)
        - Для старых генераций С кодом: не трогаем
        """
        # 1. Проверяем нужно ли генерировать s_hash_id:
        # - ИЛИ это новый объект (self.pk == None)
        # - ИЛИ это старый объект без s_hash_id (миграция)
        if not self.pk or not self.s_hash_id:
            # Если это новая генерация, сначала сохраняем её, чтобы получить ID
            if not self.pk:
                # Сохраняем БЕЗ s_hash_id чтобы Django создал запись и присвоил pk
                super().save(*args, **kwargs)
                # После save() Django автоматически заполнит self.pk

            # Кодируем pk в компактный, необратимый код
            # Пример: pk=42 → "QBErd8"
            self.s_hash_id = Hashids(salt=HASHIDS_SALT, min_length=HASHIDS_MIN_LENGTH).encode(self.pk)

            # Сохраняем только поле s_hash_id (не перезаписываем остальное)
            super().save(update_fields=['s_hash_id'])
        else:
            # Объект существует И уже имеет s_hash_id: сохраняем как обычно
            # Не трогаем s_hash_id, он был сформирован при создании
            super().save(*args, **kwargs)


class TbVote(models.Model):
    """
    Анонимный учет голосов (лайков, жалоб, авторства) без сохранения ПДн.

    Поля:
    • id: первичный ключ записи (BigAutoField, 8 байт, до ~9×10¹⁸)
    • k_item: ключ объекта (foreign key), за который голосуют
    • i_direction: направление голоса (лайк, жалоба или голос автора)
    • s_fingerprint: хэш-отпечаток клиент/браузер/секрет для защиты от накрутки
    • d_created_at: дата и время фиксации голоса
    """

    class Direction(models.IntegerChoices):
        LIKE = VOTE_LIKE, 'Like (+1)'
        CLAIM = VOTE_CLAIM, 'Claim (-2)'
        AUTHOR = VOTE_AUTHOR, 'Author Like (+2)'

    id = models.BigAutoField(
        primary_key=True,
        verbose_name="ID",
        help_text="Первичный ключ (BigAutoField, 8 байт)",
    )
    k_item = models.ForeignKey(
        TbHypn0Item,
        on_delete=models.CASCADE,
        related_name="votes",
        verbose_name="Картина",
    )
    i_direction = models.IntegerField(
        choices=Direction.choices,
        default=Direction.LIKE,
        verbose_name="Направление",
        help_text="Направление голоса",
    )
    s_fingerprint = models.CharField(
        max_length=64,
        db_index=True,
        verbose_name="Хэш устройства/отпечаток",
        help_text="SHA256(visitor_uuid + SECRET_KEY) для защиты от накрутки и разделения устройств",
    )
    d_created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Дата голосования",
    )

    class Meta:
        verbose_name = "Голос/Лайк"
        verbose_name_plural = "Голоса/Лайки"
        constraints = [
            models.UniqueConstraint(
                fields=["k_item", "s_fingerprint"],
                name="unique_item_fingerprint_vote",
            )
        ]
        ordering = ["-d_created_at"]

    def __str__(self) -> str:
        return f"Голос за {self.k_item.s_hash_id} [{self.s_fingerprint[:8]}...]"


class TbBlogPost(models.Model):
    """
    Статьи блога, документация и инфо-страницы (Privacy Policy и др.).

    Поля:
    • id: первичный ключ статьи (SmallAutoField, 2 байта, до 32 767 записей)
    • s_title: заголовок статьи (HTML)
    • slug: слаг (URI-адрес) статьи
    • s_teaser: тизер статьи (HTML)
    • s_content: основной текст статьи (HTML)
    • f_cover_img: картинка обложки статьи
    • is_published: флаг публикации
    • d_published_at: дата и время публикации
    • d_created_at: дата создания записи
    • d_updated_at: дата обновления записи
    """
    id = models.SmallAutoField(
        primary_key=True,
        verbose_name="ID",
        help_text="Первичный ключ (SmallAutoField, до 32 767 записей)",
    )
    s_title = models.CharField(
        max_length=255,
        help_text="HTML-заголовок (с HTML-тегами, типографированный etpgrf)",
        verbose_name="Заголовок",
    )
    slug = models.SlugField(
        max_length=200,
        unique=True,
        verbose_name="URL-слаг",
    )
    s_teaser = models.TextField(
        max_length=1024,
        blank=True,
        help_text="HTML-контент тизера, очищенный и типографированный etpgrf",
        verbose_name="Краткое описание / Лид",
    )
    s_content = models.TextField(
        help_text="HTML-контент статьи, очищенный и типографированный etpgrf",
        verbose_name="Основной HTML-контент",
    )
    f_cover_img = models.ImageField(
        upload_to="blog/covers/%Y/",
        blank=True,
        null=True,
        verbose_name="Обложка",
    )

    is_published = models.BooleanField(
        default=False,
        verbose_name="Опубликовано",
    )
    d_published_at = models.DateTimeField(
        default=timezone.now,
        db_index=True,
        verbose_name="Дата публикации",
    )
    d_created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Дата создания",
    )
    d_updated_at = models.DateTimeField(
        auto_now=True,
        verbose_name="Дата обновления",
    )

    class Meta:
        verbose_name = "Статья блога / Страница"
        verbose_name_plural = "Статьи блога / Страницы"
        ordering = ["-d_published_at", "-d_created_at"]

    def __str__(self) -> str:
        return self.s_title
