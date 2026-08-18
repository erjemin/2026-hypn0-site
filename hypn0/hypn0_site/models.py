from django.db import models
from hypn0.settings import *

class TbHypn0Item(models.Model):
    """Единая модель для генераций, публичных шеров и витрины галереи."""
    class Level(models.IntegerChoices):
        CANDIDATE = LVL_CANDIDATE, 'Шум сознания'              # Свежая генерация. Запрет на удаление до Х дней.
        LEVEL_1 = LVL_PRE_MODERATED, 'Плеск бессознательного'  # Есть "лайки", не проверено, можно удалять при низком score
        LEVEL_2 = LVL_MODERATED, 'Одобрено Мозговым Слизнем'   # Есть "лайки", проверено, можно удалять при низком score
        IMMORTAL = LVL_LOCK_FOR_DELETION, 'Глубокий транс'     # Нельзя удалять, даже при низком score

    s_hash_id = models.CharField(
        max_length=16,
        unique=True,
        db_index=True,
        verbose_name="Хэш-идентификатор",
    )
    s_title = models.CharField(
        max_length=255,
        verbose_name="Название картины",
    )
    file_svg = models.FileField(
        upload_to="svg/%Y/%m/",
        verbose_name="SVG-файл",
    )
    i_sha1 = models.CharField(
        max_length=40,
        verbose_name="SHA1",
        )
    i_file_size = models.PositiveIntegerField(
        default=0,
        help_text="Размер файла в байтах",
        verbose_name="Размер файла",
    )

    # Снимок параметров для возможного клонирования настроек
    j_params = models.JSONField(
        default=dict,
        blank=True,
        verbose_name="Параметры генерации",
        help_text="Метаданные и параметры для возможного клонирования настроек",
    )

    # Популярность
    i_likes_count = models.PositiveIntegerField(
        default=0,
        db_index=True,
        verbose_name="Количество лайков",
    )
    i_views_count = models.PositiveIntegerField(
        default=0,
        verbose_name="Количество просмотров",
    )
    i_reports_count = models.PositiveIntegerField(
        default=0,
        verbose_name="Количество жалоб",
    )
    f_score = models.FloatField(
        default=0.0,
        db_index=True,
        help_text="Рейтинг для Smart Retention",
        verbose_name="Рейтинг популярности",
    )

    # Модерация
    i_level = models.IntegerField(
        choices=Level.choices,
        default=Level.CANDIDATE,
        help_text="Уровень доступа",
        verbose_name="Уровень доступа",
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


class TbVote(models.Model):
    """Анонимный учет голосов (лайков) без сохранения ПДн."""

    k_item = models.ForeignKey(
        TbHypn0Item,
        on_delete=models.CASCADE,
        related_name="votes",
        verbose_name="Картина",
    )
    s_fingerprint = models.CharField(
        max_length=64,
        db_index=True,
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
        return f"Голос за {self.k_item.hash_id} [{self.s_fingerprint[:8]}...]"


class TbBlogPost(models.Model):
    """
    Статьи блога, документация и инфо-страницы (Privacy Policy и др.).

    + виртуальные поля для управления типографом etpgrf
    """

    s_title = models.CharField(
        max_length=200,
        help_text="HTML-заголовок, очищенный и типографированный etpgrf",
        verbose_name="Заголовок",
    )
    slug = models.SlugField(
        max_length=200,
        unique=True,
        verbose_name="URL-слаг",
    )
    s_summary = models.TextField(
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
        null=True,
        blank=True,
        db_index=True,
        verbose_name="Дата публикации",
    )
    d_created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Дата создания",
    )
    d_created_at = models.DateTimeField(
        auto_now=True,
        verbose_name="Дата обновления",
    )

    class Meta:
        verbose_name = "Статья блога / Страница"
        verbose_name_plural = "Статьи блога / Страницы"
        ordering = ["-d_published_at", "-d_created_at"]

    def __str__(self) -> str:
        return self.s_title
