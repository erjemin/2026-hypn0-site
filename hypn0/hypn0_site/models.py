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
        CANDIDATE = 0, 'Candidate: Шум сознания'             # Свежая генерация. Запрет на удаление до Х дней.
        LEVEL_1 = 10, 'Voted: Плеск бессознательного'     # Прогрето, есть "лайки", не проверено модератором, можно удалять при низком score
        LEVEL_2 = 30, 'Moderated: Одобрено Мозговым Слизнем'  # Есть "лайки", проверено, можно удалять при низком score
        IMMORTAL = 1000, 'Locked: Глубокий транс'       # Нельзя удалять, даже при низком score
        # Отрицательные / проблемные уровни (аномалии)
        SHAMED = -20, 'Шейминг (аномальный наплыв жалоб)'
        SUSPICIOUS = -10, 'Подозрение на накрутку (спайк лайков)'

    id = models.AutoField(
        primary_key=True,
        verbose_name="ID",
        help_text="Первичный ключ (~2.14 млрд записей, 4 байта)",
    )
    s_hash_id = models.CharField(
        max_length=16,
        unique=True,
        editable=False,
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
        default=1,
        db_index=True,
        verbose_name="Лайков",
        help_text="Число лайков гипнотической SVG-картины. Поле используется для отображения в интерфейсе. Для расчета"
                  " рейтинга популярности намеренно НЕ ИСПОЛЬЗУЕТСЯ. Рейтинг будет рассчитан на основе таблицы"
                  " <tt>Голоса/Лайка</tt> с учетом весов лайков и клаймов.",
    )
    i_views_count = models.PositiveIntegerField(
        default=1,
        verbose_name="Просмотров",
    )
    i_claims_count = models.PositiveIntegerField(
        default=0,
        verbose_name="Жалоб",
        help_text="Число жалоб на гипнотическую SVG-картину. Поле используется для отображения в интерфейсе. Для расчета"
                  " рейтинга популярности намеренно НЕ ИСПОЛЬЗУЕТСЯ. Рейтинг будет рассчитан на основе таблицы"
                  " <tt>Голоса/Лайка</tt> с учетом весов лайков и клаймов.",
    )
    f_score = models.FloatField(
        default=0.0,
        db_index=True,
        verbose_name="Рейтинг",
        help_text="Рейтинг для Smart Retention и определения, что удалять при чистке по лимитам, а что оставлять",
    )

    # Модерация
    i_level = models.IntegerField(
        choices=Level.choices,
        default=Level.CANDIDATE,
        verbose_name="Уровень",
        help_text="В какой группе находится SVG-файл генерации",
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

    @property
    def card_bg_style(self) -> str:
        """
        Вычисляет утонченную палитру подложки карточки на основе цвета гипноточки.
        
        Использует CSS-переменные для бесшовной адаптации под текущую тему зрителя (светлая/темная):
        - Экстремально светлые точки (luminance >= 215, напр. чисто белый): всегда темный фон.
        - Экстремально темные точки (luminance <= 40, напр. чисто черный): всегда светлый фон.
        - Цветные/промежуточные оттенки (40 < luminance < 215): изящный тинт цвета точки,
          который гармонично подстраивается под светлую и темную тему зрителя.
        """
        color_hex = "#a855ff"
        if isinstance(self.j_metadata, dict):
            color_hex = self.j_metadata.get("color", "#a855ff") or "#a855ff"

        # Нормализация HEX
        hex_clean = color_hex.lstrip("#")
        if len(hex_clean) == 3:
            hex_clean = "".join([c * 2 for c in hex_clean])
        elif len(hex_clean) != 6:
            hex_clean = "a855ff"

        try:
            r = int(hex_clean[0:2], 16)
            g = int(hex_clean[2:4], 16)
            b = int(hex_clean[4:6], 16)
        except ValueError:
            r, g, b = 168, 85, 255

        # Перцептивная яркость (ITU-R BT.601)
        luminance = 0.299 * r + 0.587 * g + 0.114 * b

        if luminance >= 215:
            # Экстремально светлая точка (белая/пастельно-белая) -> принудительно темный графит в обеих темах
            dark_bg = f"rgb({max(8, int(r * 0.05))}, {max(8, int(g * 0.05))}, {max(12, int(b * 0.06))})"
            return f"--card-bg-light: {dark_bg}; --card-bg-dark: {dark_bg};"
        elif luminance <= 40:
            # Экстремально темная точка (черная/глубокая смола) -> принудительно шелково-светлый в обеих темах
            light_bg = f"rgb({min(248, int(244 + r * 0.03))}, {min(248, int(244 + g * 0.03))}, {min(250, int(246 + b * 0.03))})"
            return f"--card-bg-light: {light_bg}; --card-bg-dark: {light_bg};"
        else:
            # Цветная точка (фиолетовый, изумрудный, бирюзовый, оранжевый и т.д.)
            # Светлая тема: мягкий шелковый фон с 3.5% тинтом цвета точки
            light_bg = f"rgb({min(250, int(245 + r * 0.035))}, {min(250, int(245 + g * 0.035))}, {min(252, int(247 + b * 0.035))})"
            # Темная тема: глубокий графитово-ночной фон с 7% тинтом цвета точки
            dark_bg = f"rgb({max(9, int(9 + r * 0.07))}, {max(9, int(9 + g * 0.07))}, {max(13, int(13 + b * 0.08))})"
            return f"--card-bg-light: {light_bg}; --card-bg-dark: {dark_bg};"

    def increment_views(self):
        """Безопасный инкремент просмотров"""
        TbHypn0Item.objects.filter(id=self.id).update(i_views_count=F('i_views_count') + 1)

    def vote(self, visitor_uuid_or_fp: str, direction: int | None = None) -> bool:
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

        if direction is None:
            direction = TbVote.Direction.LIKE

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

    def save(self, *args, visitor_uuid_or_fp: str | None = None, **kwargs):
        """
        Переопределенный метод save для TbHypn0Item.

        ПРАВИЛА И СЦЕНАРИИ СОХРАНЕНИЯ:
        ------------------------------
        1. Создание новой картины (is_new=True):
           - Создание возможно ТОЛЬКО с фронтенда при наличии согласия на отслеживание (visitor_uuid_or_fp).
           - Если пользователь не "подчинился Гипножабе" (visitor_uuid_or_fp отсутствует), создание БЛОКИРУЕТСЯ
             выбрасыванием PermissionError (защита от сохранения анонимных работ без автора).
           - В рамках одной атомарной транзакции:
             а) Сохраняется запись картины и генерируется self.pk.
             б) Генерируется криптографический s_hash_id.
             в) Создается обязательная авторская запись TbVote(Direction.AUTHOR).
             г) Стартовый счетчик i_likes_count по умолчанию равен 1.

        2. Редактирование существующей картины (is_new=False, например из Django Admin):
           - Картина уже существует в БД (self.pk есть).
           - Разрешено обычное обновление любых полей (название, уровень модерации, рейтинг и т.д.).
           - Никакие авторские записи повторно не создаются.
        """
        is_new = self.pk is None

        # 0. Блокировка создания новой картины без подчинения Гипножабе
        if is_new and not visitor_uuid_or_fp:
            raise PermissionError("Создание картины запрещено: пользователь не подчинился Гипножабе (отсутствует visitor UUID)")

        # 1. Вычисляем хэш автора для новой картины
        author_fp = None
        if is_new and visitor_uuid_or_fp:
            if len(visitor_uuid_or_fp) == 64:
                author_fp = visitor_uuid_or_fp
            else:
                author_fp = hashlib.sha256(f"{visitor_uuid_or_fp}:{SECRET_KEY}".encode()).hexdigest()

        with transaction.atomic():
            # 2. Сохраняем объект в базу (для новых записей СУБД присваивает self.pk)
            super().save(*args, **kwargs)

            # 3. Формируем s_hash_id, если его еще нет
            if not self.s_hash_id:
                self.s_hash_id = Hashids(salt=HASHIDS_SALT, min_length=HASHIDS_MIN_LENGTH).encode(self.pk)
                super().save(update_fields=['s_hash_id'])

            # 4. Регистрируем автора в TbVote (гарантированно после получения self.pk)
            if is_new and author_fp:
                TbVote.objects.create(
                    k_item=self,
                    i_direction=TbVote.Direction.AUTHOR,
                    s_fingerprint=author_fp,
                )


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
        LIKE = 1, 'Like (+1)'
        CLAIM = -2, 'Claim (-2)'
        AUTHOR = 2, 'Author Like (+2)'

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
        blank=True,
        default="",
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
