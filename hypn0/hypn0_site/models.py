from django.db import models


class HalftoneItem(models.Model):
    """Единая модель для генераций, публичных шеров и витрины галереи."""

    hash_id = models.CharField(
        max_length=16,
        unique=True,
        db_index=True,
        verbose_name="Хэш-идентификатор",
    )
    title = models.CharField(
        max_length=150,
        verbose_name="Название картины",
    )
    svg_file = models.FileField(
        upload_to="svg/%Y/%m/",
        verbose_name="SVG-файл",
    )

    # Снимок параметров для возможного клонирования настроек
    params_json = models.JSONField(
        default=dict,
        blank=True,
        verbose_name="Параметры генерации",
    )
    file_size = models.PositiveIntegerField(
        default=0,
        help_text="Размер файла в байтах",
        verbose_name="Размер файла",
    )

    # Популярность и модерация
    likes_count = models.PositiveIntegerField(
        default=0,
        db_index=True,
        verbose_name="Количество лайков",
    )
    views_count = models.PositiveIntegerField(
        default=0,
        verbose_name="Количество просмотров",
    )
    reports_count = models.PositiveIntegerField(
        default=0,
        verbose_name="Количество жалоб",
    )
    score = models.FloatField(
        default=0.0,
        db_index=True,
        help_text="Рейтинг для Smart Retention",
        verbose_name="Рейтинг популярности",
    )

    is_curated = models.BooleanField(
        default=False,
        help_text="Выбор модератора / галерея (иммунитет к удалению)",
        verbose_name="Выбор редакции",
    )
    is_public = models.BooleanField(
        default=True,
        help_text="Доступность по прямой ссылке",
        verbose_name="Публичный доступ",
    )

    # Промо-блок (на перспективу)
    promo_url = models.URLField(
        blank=True,
        default="",
        verbose_name="Промо-ссылка",
    )
    promo_title = models.CharField(
        max_length=100,
        blank=True,
        default="",
        verbose_name="Бейдж/автор промо",
    )
    promo_clicks = models.PositiveIntegerField(
        default=0,
        verbose_name="Клики по промо",
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
        db_index=True,
        verbose_name="Дата создания",
    )

    class Meta:
        verbose_name = "Гипно-картина"
        verbose_name_plural = "Гипно-картины"
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"{self.title} ({self.hash_id})"


class HalftoneVote(models.Model):
    """Анонимный учет голосов (лайков) без сохранения ПДн."""

    item = models.ForeignKey(
        HalftoneItem,
        on_delete=models.CASCADE,
        related_name="votes",
        verbose_name="Картина",
    )
    fingerprint = models.CharField(
        max_length=64,
        db_index=True,
        help_text="SHA256(visitor_uuid + SECRET_KEY) для защиты от накрутки и разделения устройств",
        verbose_name="Хэш устройства/отпечаток",
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Дата голосования",
    )

    class Meta:
        verbose_name = "Голос / Лайк"
        verbose_name_plural = "Голоса / Лайки"
        constraints = [
            models.UniqueConstraint(
                fields=["item", "fingerprint"],
                name="unique_item_fingerprint_vote",
            )
        ]
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"Голос за {self.item.hash_id} [{self.fingerprint[:8]}...]"


class BlogPost(models.Model):
    """
    Статьи блога, документация и инфо-страницы (Privacy Policy и др.).

    + виртуальные поля для управления типографом etpgrf
    """

    title = models.CharField(
        max_length=200,
        help_text="HTML-заголовок, очищенный и типографированный etpgrf",
        verbose_name="Заголовок",
    )
    slug = models.SlugField(
        max_length=200,
        unique=True,
        verbose_name="URL-слаг",
    )
    summary = models.TextField(
        max_length=500,
        blank=True,
        help_text="HTML-контент тизера, очищенный и типографированный etpgrf",
        verbose_name="Краткое описание / Лид",
    )
    content = models.TextField(
        help_text="HTML-контент статьи, очищенный и типографированный etpgrf",
        verbose_name="Основной HTML-контент",
    )
    cover_image = models.ImageField(
        upload_to="blog/covers/%Y/",
        blank=True,
        null=True,
        verbose_name="Обложка",
    )

    is_published = models.BooleanField(
        default=False,
        verbose_name="Опубликовано",
    )
    published_at = models.DateTimeField(
        null=True,
        blank=True,
        db_index=True,
        verbose_name="Дата публикации",
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Дата создания",
    )
    updated_at = models.DateTimeField(
        auto_now=True,
        verbose_name="Дата обновления",
    )

    class Meta:
        verbose_name = "Статья блога / Страница"
        verbose_name_plural = "Статьи блога / Страницы"
        ordering = ["-published_at", "-created_at"]

    def __str__(self) -> str:
        return self.title
