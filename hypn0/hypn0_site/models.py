from django.db import models
from hashids import Hashids
from hypn0.settings import *
from django.utils import timezone

class TbHypn0Item(models.Model):
    """
    МодельЕдиная модель для генераций, публичных шеров и витрины галереи.

    Поля:
    • id: идентификатор записи (стандартное поле Django)
    • s_hash_id: хэш-сумма шеринга для SVG-генерации
    • s_title: Заголовок (до 255 символов, разрешен HTML)
    • file_svg: SVG-файл генерации
    • i_sha1: контрольная сумма (SHA1-хэш файла)
    • i_file_size: размер файла
    • j_metadata: метаданные файла JSON (например, для хранения параметров генерации)
    • i_likes_count: количество лайков
    • i_views_count: количество просмотров
    • i_claims_count: количество жалоб/претензий (дислайков)
    • f_score: оценка для стратегии хранения и умной очистки (Smart Retention)
    • i_level: уровень хранения (свежее, модерированное, защищенное от удаления)
    • is_public: публичный (доступный по внешней ссылке)
    • s_author_fingerprint: хеш-код браузера автора
    • s_promo_url: промо-ссылка (с дополнительной об авторе-спонсоре)
    • s_promo_title: заголовок промо-ссылки или бейджа
    • i_promo_clicks: количество кликов по промо-ссылке
    • d_created_at: дата создания записи
    • d_updated_at: дата последнего обновления записи

    Методы:
    • save(): формирование s_hash_id
    """
    class Level(models.IntegerChoices):
        CANDIDATE = LVL_CANDIDATE, 'Candidate: Шум сознания'             # Свежая генерация. Запрет на удаление до Х дней.
        LEVEL_1 = LVL_PRE_MODERATED, 'Voted: Плеск бессознательного'     # Есть "лайки", не проверено, можно удалять при низком score
        LEVEL_2 = LVL_MODERATED, 'Moderated: Одобрено Мозговым Слизнем'  # Есть "лайки", проверено, можно удалять при низком score
        IMMORTAL = LVL_LOCK_FOR_DELETION, 'Locked: Глубокий транс'       # Нельзя удалять, даже при низком score

    s_hash_id = models.CharField(
        max_length=16,
        unique=True,
        db_index=True,
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
    i_sha1 = models.CharField(
        max_length=40,
        verbose_name="SHA1",
        help_text="SHA1 хэш результирующего SVG-файла",
        )
    i_file_size = models.PositiveIntegerField(
        default=0,
        verbose_name="Размер файла",
        help_text="Размер файла в байтах",
    )

    # НА ВСЯИЙ СЛУЧАЙ: Метаданные и снимок параметров для возможного клонирования настроек
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
    )
    i_views_count = models.PositiveIntegerField(
        default=0,
        verbose_name="Число просмотров",
    )
    i_claims_count = models.PositiveIntegerField(
        default=0,
        verbose_name="Число жалоб",
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

    # Автор
    s_author_fingerprint = models.CharField(
        max_length=64,
        db_index=True,   # ??? -- подумать нужно или нет
        help_text="SHA256(visitor_uuid + SECRET_KEY) для защиты от накрутки и разделения устройств",
        verbose_name="Хэш устройства/отпечаток",
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
        TbHypn0Item.objects.get(id=self.id).update(i_views_count=F('i_views_count') + 1)

    def increment_likes(self):
        """Безопасный инкремент лайков"""
        TbHypn0Item.objects.get(id=self.id).update(i_likes_count=F('i_likes_count') + 1)
        # Здесь будет код для записи в TbVote

    def increment_claims(self):
        """Безопасный инкремент жалоб"""
        TbHypn0Item.objects.get(id=self.id).update(i_claims_count=F('i_claims_count') + 1)
        # Здесь будет код для записи в TbVote

    def increment_promo_clicks(self):
        """Безопасный инкремент кликов по промо"""
        TbHypn0Item.objects.get(id=self.id).update(i_promo_clicks=F('i_promo_clicks') + 1)

    def rescore(self):
        """Пересчет рейтинга i_promo_clicks
        Для оптимизации диска на сервере используется динамическая очистка на основе рейтинга популярности
        («гравитации»), а не слепой Х-дневный таймер:
        $$\text{Score} = \frac{\text{Likes} + \text{Bonus}_{\text{moderator}}}{(\text{Age in hours} + 2)^\gamma}$$
        """
        age_ih_hours = (timezone.now() - self.d_created_at).total_seconds() / 3600 + 1
        new_score = (self.i_likes_count + self.i_level) / ((age_ih_hours + 2) ** GAMMA)
        TbHypn0Item.objects.get(id=self.id).update(f_score=new_score)

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
            # Оффер существует И уже имеет s_hash_id: сохраняем как обычно
            # Не трогаем s_hash_id, он был сформирован при создании
            super().save(*args, **kwargs)


class TbVote(models.Model):
    """
    Анонимный учет голосов (лайков) без сохранения ПДн.

    Поля:
    • k_item: ключ объекта (foreign key), за который голосуют
    • i_direction: направление голоса
    • s_fingerprint: Хэш-отпечаток клиент/браузер/secret для защиты он накрутки
    • d_created_at: дата создания
    """

    class Direction(models.IntegerChoices):
        LIKE = VOTE_LIKE, 'Like'
        CLIME = VOTE_CLAIM, 'Clime'

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
        db_index=True,   # ??? -- подумать нужно или нет
        help_text="SHA256(visitor_uuid + SECRET_KEY) для защиты от накрутки и разделения устройств",
        verbose_name="Хэш устройства/отпечаток",
    )
    d_created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Дата голосования",
    )

    class Meta:
        verbose_name = "Голос / Лайк"
        verbose_name_plural = "Голоса / Лайки"
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
    • s_title: Заголовок статьи (HTML).
    • slug: Слаг (URI-адрес) статьи.
    • s_teaser: Тизер статьи (HTML).
    • s_content: Текст статьи (HTML).
    • f_cover_img: Картинка обложки статьи.
    • is_published: Опубликована ли статья.
    • d_published_at: Дата публикации статьи.
    • d_created_at: Дата создания статьи.
    • d_updated_at: Дата обновления статьи.

    + а в админке виртуальные поля для управления типографом etpgrf
    """

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
