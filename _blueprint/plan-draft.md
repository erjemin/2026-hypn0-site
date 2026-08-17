# План: Django микросайт для генерации гипно-SVG

## Стек
- **Django 5.x** — бэкенд
- **HTMX** — интерактивность без перезагрузки
- **Pillow** — обработка изображений, color clustering
- **scikit-learn** — k-means для дуотон/трейтон/квантование
- **numpy** — векторизованные вычисления
- **Gunicorn** — WSGI-сервер
- **Poetry** — управление зависимостями

## Структура проекта (как в cadpoint-ru)

```
2026-hypn0-site/
├── pyproject.toml                     # Poetry — общие зависимости
├── poetry.lock
├── .env.sample                        # Переменные окружения
├── .env                               # Локальные секреты (не в VCS)
├── Dockerfile                         # Многостадийная сборка
├── docker-compose.local.yml           # Dev: bind-mount, --reload
├── docker-compose.prod.yml            # Prod: образ из registry
│
├── config/
│   └── nginx/                         # Nginx-конфиги (хост, не в Docker)
│       └── hypn0-app--external-nginx.conf
│
├── public/                            # Статика + медиа (shared dev/prod)
│   ├── static/
│   │   ├── css/
│   │   │   └── site.css               # Tailwind CDN + кастомные стили
│   │   └── js/
│   │       └── site.js                # Alpine/минимальный JS
│   └── media/
│       ├── temp/              # Публичные SVG (TTL 14 дней)
│       └── gallery/           # Отфильтрованные лучшие
│
├── database/                          # SQLite БД
│   └── .gitignore
│
├── hypn0/                             # Django project root
│   ├── manage.py
│   ├── hypn0/                         # Settings package
│   │   ├── __init__.py
│   │   ├── settings.py                # django-environ для конфига
│   │   ├── urls.py
│   │   ├── wsgi.py
│   │   └── templates/
│   │       ├── base.html
│   │       └── errors/
│   │           ├── 404.html
│   │           └── 500.html
│   │
│   └── halftone/                      # Django app
│       ├── __init__.py
│       ├── urls.py
│       ├── views.py                   # главная + генерация
│       ├── forms.py                   # формы параметров
│       ├── models.py                  # FeaturedSVG + votes
│       ├── services/
│       │   ├── __init__.py
│       │   └── halftone.py            # ядро из main.py
│       ├── templates/
│       │   └── halftone/
│       │       └── index.html
│       └── management/
│           └── commands/
│               ├── cleanup_temp.py      # очистка temp (14 дней)
│               └── cleanup_reports.py   # удаление по жалобам
│
├── .gitea/workflows/                  # CI/CD
│   └── docker-publish.yaml
│
└── main.py                            # [удаляем]
```

## Ключевые принципы (перенос из cadpoint-ru)

| Принцип       | Реализация                               |
|---------------|------------------------------------------|
| Django-проект | `hypn0/` — подкаталог в корне            |
| Статика/медиа | `public/static/` и `public/media/`       |
| БД            | `database/db.sqlite3`                    |
| Конфиги       | `config/nginx/` — внешний nginx          |
| Docker        | многостадийный, bind-mount для dev       |
| Зависимости   | Poetry, `pyproject.toml` в корне         |
| Env           | `django-environ`, `.env.sample` → `.env` |

## Архитектура приложения

### 1. Рефакторинг ядра (`hypn0/halftone/services/halftone.py`)

Извлечь из `main.py` чистую функцию:

```python
def generate_halftone_svg(
    image: Image.Image,
    *,
    cols: int = 80,
    max_radius: int = 8,
    color: str = "#800000",
    opacity: str = "90",          # hex alpha для CSS
    animation_variants: int = 12,
) -> str:  # возвращает SVG-строку
```

**Что убираем из CLI-версии:**
- Аргументы `image_path` / `output_path`
- Форматирование чисел для CSS-переменных
- Запись в файл
- `print()`

### 2. View-слой (`hypn0/halftone/views.py`)

```python
# Главная — GET → рендерим index.html
# Генерация — POST (HTMX) → возвращаем SVG фрагмент
# Скачивание — GET /download/{temp_id} → отдаём файл + удаляем исходник
# Просмотр публичного — GET /view/{hash} → отдаём SVG из temp/
# Галерея — GET /gallery → список FeaturedSVG
# Просмотр в галерее — GET /gallery/{hash}
# Report — POST /report/{hash} → increment reports_count
# Promote (admin) — админ переносит SVG из temp → gallery
```

### 3. Фронтенд (`hypn0/halftone/templates/halftone/index.html`)

```
┌──────────────────────────────────────────────┐
│  📷 [Загрузить изображение]                  │
│  hx-post="/generate"                         │
│  hx-target="#preview"                        │
├──────────────────────────────────────────────┤
│  Ширина колонок: [80]                        │
│  Макс. размер:   [8]                         │
│  Цвет:           [#800000]                   │
│  Анимация:       [✓]                         │
│  Опубликовать:  [ ] — показать ссылку        │
├──────────────────────────────────────────────┤
│  [Сгенерировать]                             │
├──────────────────────────────────────────────┤
│  <div id="preview"></div>                    │
│  <div id="actions" class="hidden">           │
│    <a id="download-link">Скачать</a>         │
│    <a id="public-link" class="hidden">🔗     │
│      Поделиться</a>                          │
│  </div>                                      │
└──────────────────────────────────────────────┘
```

Важно: данная форма -- черновик. Настроек генерации будет больше:
- Фигуры (не только кружки, но и квадратики, кольца, треугольники, буквы-цифры, линии (переменной толщины), волнистые линии.
- Наклон сетки (угол)
- Цветовые модели (дуотон/трейтон с разным наклоном сетки для каждого цвета как в полиграфии, полноцвет)
- Возможно разные настройки анимации (групп)

Рядом с панелью настроек, превью ("на лету") и кнопка скачать.
Галерея отобранных изображений. Под картинками в галере кнопки "понравилось" и "подаваться"

## СЕКЦИЯ B: Алгоритмы и фигуры

### F: Типы фигур

| ID         | Фигура                 | Параметры                    | SVG-реализация                                  |
|------------|------------------------|------------------------------|-------------------------------------------------|
| `circle`   | Круг                   | `max_radius`                 | `<circle r="..."/>`                             |
| `square`   | Квадрат                | `max_size`                   | `<rect x="-r" y="-r" width="2r" height="2r"/>`  |
| `ring`     | Кольцо                 | `max_radius`, `stroke_width` | `<circle r="..." fill="none" stroke="..."/>`    |
| `diamond`  | Ромб                   | `max_size`                   | `<polygon points="0,-r -r,0 0,r r,0"/>`         |
| `star`     | Звезда 5-лучевая       | `outer_r`, `inner_r`         | `<polygon points="..."/>`                       |
| `cross`    | Крест                  | `max_size`, `arm_width`      | `<path d="..."/>`                               |
| `line-h`   | Горизонтальная полоска | `max_width`, `thickness`     | `<rect x="-r" y="-t/2" width="2r" height="t"/>` |
| `line-v`   | Вертикальная полоска   | `max_height`, `thickness`    | `<rect x="-t/2" y="-r" width="t" height="2r"/>` |
| `line-d`   | Диагональная полоска   | `max_length`, `thickness`    | Повернутый `<rect/>` на angle                   |
| `wave`     | Волна                  | `amplitude`, `frequency`     | `<path d="M 0 0 Q r/2 -a r 0 ..."/>`            |
| `hex`      | Шестигранник           | `max_radius`                 | `<polygon points="..."/>` (6 вершин)            |
| `triangle` | Треугольник            | `max_size`                   | `<polygon points="0,-r -r,r r,r"/>`             |
| `typeface` | Буква/цифра            | `font_family`, `font_size`   | `<text>...</text>`                              |

**Сложность реализации:**
- **Быстро** (фигура по центру, один параметр масштаба): circle, square, ring, diamond, hex, triangle
- **Средне** (дополнительные параметры): line-h/v/d, cross, star, wave
- **Сложно** (загрузка шрифта): typeface

### G: Типы сеток

| ID          | Описание                          | Параметры           | Сложность |
|-------------|-----------------------------------|---------------------|-----------|
| `grid`      | Прямая прямоугольная (как сейчас) | `cols`, `rows`      | —         |
| `rotated`   | Прямая сетка с наклоном           | `cols`, `angle_deg` | Низкая    |
| `hex_grid`  | Шестиугольная сетка               | `cols`, `radius`    | Средняя   |
| `isometric` | Изометрическая проекция 60°       | `cols`              | Средняя   |
| `polar`     | Полярные координаты               | `rings`, `spokes`   | Высокая   |
| `bend`      | Изогнутая сетка                   | `cols`, `curve`     | Высокая   |

**Реализация `rotated`:**
```python
angle = math.radians(angle_deg)
cos_a, sin_a = math.cos(angle), math.sin(angle)
rotated_x = x * cos_a - y * sin_a
rotated_y = x * sin_a + y * cos_a
```

### P: Цветовые модели

| ID             | Описание              | Параметры                     | Сложность |
|----------------|-----------------------|-------------------------------|-----------|
| `single`       | Один цвет             | `color_hex`, `opacity`        | —         |
| `duotone`      | 2 цвета               | `color_a`, `color_b`, `blend` | Средняя   |
| `tritone`      | 3 цвета               | `colors[3]`, `blend`          | Средняя   |
| `quad`         | 4 цвета               | `colors[4]`, `blend`          | Средняя   |
| `palette_auto` | Авто-палитра n цветов | `palette_name`, `n`           | Низкая    |
| `fullcolor`    | Квантование цветов    | `quantization_levels`         | Высокая   |

**Реализация `duotone/tritone/quad`:**
```python
from sklearn.cluster import KMeans
pixels = image.convert('RGB').resize((100, 100)).getdata()
kmeans = KMeans(n_clusters=n, random_state=42, n_init=1)
kmeans.fit(pixels)
centers = kmeans.cluster_centers_  # RGB-координаты кластеров
# Каждый пиксель маппим на ближайший кластер
```

**Реализация `fullcolor`:**
```python
# Median-cut квантование
pixels = image.quantize(colors=256)  # или custom median-cut
```

### Q: Анимации

| ID        | Описание                         | Параметры                                     |
|-----------|----------------------------------|-----------------------------------------------|
| `pulse`   | Пульсация (как сейчас)           | `speed`, `variants`, `scale_min`, `scale_max` |
| `rotate`  | Медленное вращение (покачивание) | `speed`, `direction` (cw/ccw)                 |
| `wave`    | Волна по вертикали (покачивание) | `amplitude`, `frequency`, `speed`             |
| `sparkle` | Мерцание fade in/out             | `variants`, `speed_range`                     |
| `flow`    | Поток в направлении              | `direction`, `speed`                          |
| `breathe` | Всё вместе "дышит"               | `speed`, `scale_range`                        |
| `static`  | Без анимации                     | —                                             |

**Реализация:**
- Каждая группа (CSS-класс) получает свой `@keyframes` + `animation-delay`
- N ключевых кадров в `<style>` блока SVG
- SVG inline — всё работает без внешних ресурсов

## СЕКЦИЯ C: UI/UX

### Лэаут страницы

```
┌───────────────────────────────────────────────────────┐
│  hypn0                                 [Галерея] [О]  │
├───────────────────┬───────────────────────────────────┤
│  ◀ Настройки      │  ▶ Превью                         │
│                   │                                   │
│  ┌──────────────┐ │  ┌─────────────────────────────┐  │
│  │  Загрузить   │ │  │  SVG-КАРТИНКА               │  │
│  └──────────────┘ │  │                             │  │
│                   │  │                             │  │
│  ─── Стиль ─────  │  │                             │  │
│  ┌─┐┌─┐┌─┐┌─┐     │  │  [♥ liked -> в галерею]    │  │
│  │●│┌─┐┌─┐┌─┐     │  └─────────────────────────────┘  │
│  └─┘└─┘└─┘└─┘     │  [Поделиться]                     │
│  circle           │                                   │
│                   │  ┌─────────────────────────────┐  │
│  ─── Сетка ─────  │  │ <svg viewBox="...">         │  │
│  ┌─┐┌─┐┌─┐┌─┐     │  │   <style>...</style>        │  │
│  │●│┌─┐┌─┐┌─┐     │  │ </svg>                      │  │
│  └─┘└─┘└─┘└─┘     │  │                             │  │
│  grid             │  │  [В клипборд] [Скачать]     │  │
│                   │  └─────────────────────────────┘  │
│  ─── Цвет ──────  │                                   │
│  ┌─┐┌─┐┌─┐┌─┐     │                                   │
│  │●│┌─┐┌─┐┌─┐     │                                   │
│  └─┘└─┘└─┘└─┘     │                                   │
│  single           │                                   │
│                   │                                   │
│  ─── Параметры ─  │                                   │
│  Колонки:     [80]│                                   │
│  Макс. размер: [8]│                                   │
│  Цвет:   #[800000]│                                   │
│  Прозрачность:[.5]│                                   │
│  Угол сетки:  [0°]│                                   │
│  Анимация:[▼pulse]│                                   │
│                   │                                   │
│ ───────────────── │                                   │
│                   │                                   │
│  [Сгенерировать]  │                                   │
│                   │                                   │
├───────────────────┴───────────────────────────────────┤
│  ───────────── Галерея ─────────────                  │
│  [thumb]    [thumb]    [thumb]    [thumb] ...         │
│  [♥ 12]    [♥ 8]     [♥ 23]    [♥ 5]              │
└───────────────────────────────────────────────────────┘
```

### Табы настроек

- На десктопе: 2 колонки — слева настройки, справа превью
- На мобильном: вертикально — превью сверху, настройки снизу
- Табы переключают секции: "Стиль / Сетка / Цвет / Параметры"
- HTMX: `hx-trigger="change"` на контролах → превью обновляется без перезагрузки

### Галерея

- `GET /gallery` — CSS Grid сетка миниатюр (3-4 колонки)
- Каждая карточка: SVG-превью (inline), кнопка ♥ (HTMX vote), кнопка поделиться
- `POST /gallery/{hash}/vote` — HTMX запрос, обновляет ♥ счётчик
- Пагинация: 24 карточки на странице
- `GET /gallery/{hash}` — полноэкранный просмотр SVG с кнопками "Скачать" и "Поделиться"

#### ВАЖНО: Оптимизация производительности рендеринга галереи (SVG-превью)
- **Проблема:** Десятки карточек с тысячами анимированных SVG-элементов могут перегрузить браузер клиента (CPU/GPU при одновременной перерисовке).
- **Решение для витрины галереи:**
  - Карточки галереи выводятся через тег `<img src="..." loading="lazy">` (изолированный контекст рендеринга).
  - Для предотвращения постоянного пожирания ресурсов анимация в SVG по умолчанию спит (`animation-play-state: paused`) и оживает только при наведении (`:hover { animation-play-state: running; }`).
  - Дополнительно на контейнерах карточек используется CSS-свойство `content-visibility: auto` для отключения рендера невидимых вне экрана карточек.
- **Выдача пользователю («Копировать» и «Скачать»):**
  - Пользователю всегда отдается «чистый» полнофункциональный SVG со стандартно запущенной анимацией (без ограничений `animation-play-state: paused`).
  - На бэкенде/сервисе при сохранении для галереи модификатор паузы/ховера может вшиваться по умолчанию либо подставляться/вырезаться на лету при выдаче пользователю.

**CSS:**
- Dev: Tailwind CDN (`<script src="https://cdn.tailwindcss.com"></script>`) + Purge content в конфиге
- Prod: `collectstatic` → `whitenoise` обслуживает скомпилированную статику

HTMX: форма с `hx-post`, `hx-encoding="multipart/form-data"` → SVG вставляется в `#preview`.

### 4. Политика хранения, приватность и модели

#### 4.1. Принципы приватности, Zero-PII и учет голосов
- **Полное отсутствие регистрации для посетителей:** Пользователи не создают аккаунты, не вводят email, пароли или личные данные. Единственный пользователь в `auth.User` — администратор сайта для входа в Django Admin.
- **Исходные растровые изображения (JPG/PNG/WEBP):** Обрабатываются исключительно в оперативной памяти (через буфер `BytesIO`) и **не сохраняются на диск сервера вообще**.
- **Куки-согласие и идентификация устройства (Cookie-токен):**
  - При согласии с правилами («Подчиниться Гипножабе!» в `allow-tracking.html`) клиенту выставляется долгоживущая анонимная кука устройства `hypn0_vid` со случайным UUID (`Max-Age=2 года`, `SameSite=Lax`, `HttpOnly`).
  - **Голосование доступно только при наличии согласия на куки:** Если посетитель не принял соглашение (кука отсутствует), голосование заблокировано интерфейсом и отклоняется бэкендом (с требованием подчиниться Гипножабе).
- **Лайки и учет голосов:**
  - **Бэкенд:** Голоса учитываются анонимно через связку `(item_id, fingerprint)`. Поле `fingerprint` формируется как необратимый хэш: `sha256(visitor_uuid + SECRET_KEY)`. Это надежно разделяет разные компьютеры в одной корпоративной сети/NAT и не содержит открытых ПДн (Zero-PII).
  - **Фронтенд:** Для быстродействия UI и исключения лишней нагрузки список лайкнутых картин дублируется локально на клиенте в **`localStorage`** (`hypn0_votes`). На базе Alpine.js выполняется мгновенная индикация проголосованных работ.
- **Соответствие GDPR / 152-ФЗ:** Персональные данные не собираются и не хранятся.

#### 4.2. Генерация названий (AI & Fallback Title)
У каждой сгенерированной картины обязательно должно быть название (title):
- **Основной способ:** Вызов через **OpenRouter API** с отправкой сильно сжатой миниатюры (thumbnail) исходного изображения в мультимодальную LLM (VLM) для распознавания сюжета и генерации забавного гипно-названия (в стиле Гипножабы/мемов).
- **Резервный способ (Fallback):** Если API OpenRouter недоступен, закончились квоты или таймаут — название генерируется локально из случайного набора гипнотических слов, эпитетов и фраз («Мерцающий транс #42», «Глаз Гипножабы», «Астральный вихрь» и т.п.).

#### 4.3. Стратегия хранения и умной очистки (Smart Retention)
Проект не выступает постоянным файлообменником или бесплатным CDN. Пользователь скачивает сгенерированный SVG для личного использования.
Для оптимизации диска на сервере используется динамическая очистка на основе рейтинга популярности («гравитации»), а не слепой 14-дневный таймер:

$$\text{Score} = \frac{\text{Likes} + \text{Bonus}_{\text{moderator}}}{(\text{Age in hours} + 2)^\gamma}$$

- **Квота хранилища:** Задается жесткий лимит объема (например, 500 МБ или N тысяч файлов).
- **Очистка (`manage.py cleanup_storage`):** При превышении лимита удаляются файлы с наименьшим `Score`.
- **Иммунитет к удалению:** Работы, отмеченные модератором (`is_curated=True` / `Bonus`), и закрепленные промо-картины сохраняются бессрочно.

#### 4.4. SEO, шеринг и коммерциализация
- **Вшивание ссылки в SVG (Zero-cost Branding):** В скачиваемый SVG на этапе генерации добавляется мета-комментарий со ссылкой на генератор (`<!-- Generated by Hypn0 Generator (https://hypn0.ru) -->` и `<metadata>`).
- **Страница просмотра (`/v/<hash>`):** Для внешнего шеринга и индексации поисковиками генерируется легкая HTML-страница с OpenGraph разметкой и кнопкой «Открыть настройки в генераторе».
- **Возможность промо/коммерциализации:** Поддержка опциональных полей (промо-ссылка, бейдж автора/спонсора, счетчик кликов).

#### 4.5. Блог, статические страницы и типографика (HTML + `etpgrf`)
- **Отказ от конвертации Markdown «на лету»:** Вместо оверхеда с парсингом Markdown статьи и инфо-страницы хранятся напрямую в формате **HTML**.
- **Очистка HTML в админке:** При вводе/сохранении в Django Admin контент проходит валидацию и санитизацию (очистку от вредоносного или мусорного HTML/инлайн-стилей).
- **Типографирование через `etpgrf`:** Для безупречной верстки текста (неразрывные пробелы, висячая пунктуация, кавычки-елочки, тире) используется библиотека типографирования **`etpgrf`**.

#### 4.6. Архитектура моделей

```python
class HalftoneItem(models.Model):
    """
    Единая модель для генераций, публичных шеров и витрины галереи.
    """
    hash_id = models.CharField(max_length=16, unique=True, db_index=True)
    title = models.CharField(max_length=150, verbose_name="Название картины")
    svg_file = models.FileField(upload_to="svg/%Y/%m/")
    
    # Снимок параметров для возможного клонирования настроек
    params_json = models.JSONField(default=dict, blank=True)
    file_size = models.PositiveIntegerField(default=0, help_text="Размер файла в байтах")

    # Популярность и модерация
    likes_count = models.PositiveIntegerField(default=0, db_index=True)
    views_count = models.PositiveIntegerField(default=0)
    reports_count = models.PositiveIntegerField(default=0)
    score = models.FloatField(default=0.0, db_index=True, help_text="Рейтинг для Smart Retention")
    
    is_curated = models.BooleanField(default=False, help_text="Выбор модератора / галерея (иммунитет к удалению)")
    is_public = models.BooleanField(default=True, help_text="Доступность по прямой ссылке")
    
    # Промо-блок (на перспективу)
    promo_url = models.URLField(blank=True, default="", verbose_name="Промо-ссылка")
    promo_title = models.CharField(max_length=100, blank=True, default="", verbose_name="Бейдж/автор")
    promo_clicks = models.PositiveIntegerField(default=0)

    created_at = models.DateTimeField(auto_now_add=True, db_index=True)


class HalftoneVote(models.Model):
    """
    Анонимный учет голосов (лайков) без сохранения ПДн.
    """
    item = models.ForeignKey(HalftoneItem, on_delete=models.CASCADE, related_name="votes")
    fingerprint = models.CharField(
        max_length=64,
        db_index=True,
        help_text="SHA256(visitor_uuid + SECRET_KEY) для защиты от накрутки и разделения устройств"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["item", "fingerprint"], name="unique_item_fingerprint_vote")
        ]


class BlogPost(models.Model):
    """
    Статьи блога, документация и инфо-страницы (Privacy Policy и др.).
    
    + виртуальные поля для управления типографом etpgrf
    """
    title = models.CharField(max_length=200, help_text="HTML-заголовок, очищенный и типографированный etpgrf")
    slug = models.SlugField(max_length=200, unique=True)
    summary = models.TextField(max_length=500, blank=True, help_text="HTML-контент тизера, очищенный и типографированный etpgrf")
    content = models.TextField(help_text="HTML-контент статьи, очищенный и типографированный etpgrf")
    cover_image = models.ImageField(upload_to="blog/covers/%Y/", blank=True, null=True)
    
    is_published = models.BooleanField(default=False)
    published_at = models.DateTimeField(null=True, blank=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

```

## Шаги реализации

### Шаг 1. Структура каталогов

Создать:
- `hypn0/` — Django project root
- `hypn0/hypn0/` — settings package
- `hypn0/halftone/` — Django app
- `public/` — static + media
- `public/media/temp/` — публичные SVG (TTL 14 дней)
- `public/media/gallery/` — лучшие SVG
- `database/` — БД
- `config/nginx/` — nginx config
- `.gitea/workflows/` — CI/CD

### Шаг 2. Зависимости в `pyproject.toml`

Добавить:
```toml
[tool.poetry.dependencies]
django = "^5.2"
django-environ = "^0.13"
gunicorn = "^25.3"
whitenoise = "^6.12"
django-htmx = "^1.21"
```

### Шаг 3. Django settings (`hypn0/hypn0/settings.py`)

```python
import environ
env = environ.Env(DEBUG=(bool, False))
environ.Env.read_env(os.path.join(BASE_DIR.parent, '.env'))

DEBUG = env('DEBUG')
SECRET_KEY = env('SECRET_KEY')

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR.parent / 'database' / 'db.sqlite3',
    }
}

STATIC_ROOT = BASE_DIR.parent / 'public' / 'static'
MEDIA_ROOT = BASE_DIR.parent / 'public' / 'media'
MEDIA_URL = '/media/'

STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'

INSTALLED_APPS += ['halftone']
ROOT_URLCONF = 'hypn0.urls'
```

### Шаг 4. Docker

**Dockerfile** (многостадийный, как в cadpoint-ru):
- Stage 1 (builder): Poetry → export → pip install
- Stage 2 (runtime): gunicorn, non-root user 1000:1000, `collectstatic`

**docker-compose.local.yml**:
- Bind-mount: `./hypn0`, `./public`, `./database`
- Gunicorn `--reload`
- Port `8051:8000`

**docker-compose.prod.yml**:
- Образ из Gitea registry
- Host port: `127.0.0.1:8051:8000`
- Watchtower для автообновления

### Шаг 5. Nginx-конфиг (`config/nginx/hypn0-app--external-nginx.conf`)

Reverse proxy: `hypn0.local` → `127.0.0.1:8051`
- Static/media раздается через Nginx (не Django)
- GZip, HTTPS (если есть cert)

### Шаг 6. CI/CD (`.gitea/workflows/docker-publish.yaml`)

Trigger: tags `v*` → build → push to Gitea registry.
Паттерн как в cadpoint-ru.

### Шаг 7. Удаление `main.py`

CLI больше не нужен.

## Файлы для создания (итого)

| Файл                                                    | Назначение             |
|---------------------------------------------------------|------------------------|
| `hypn0/manage.py`                                       | Django CLI             |
| `hypn0/hypn0/__init__.py`                               | Settings pkg           |
| `hypn0/hypn0/settings.py`                               | Конфиг                 |
| `hypn0/hypn0/urls.py`                                   | URL routing            |
| `hypn0/hypn0/wsgi.py`                                   | WSGI entry             |
| `hypn0/hypn0/templates/base.html`                       | Базовый шаблон         |
| `hypn0/halftone/__init__.py`                            | App pkg                |
| `hypn0/halftone/urls.py`                                | URL app                |
| `hypn0/halftone/views.py`                               | Views                  |
| `hypn0/halftone/forms.py`                               | Forms                  |
| `hypn0/halftone/models.py`                              | FeaturedSVG            |
| `hypn0/halftone/services/halftone.py`                   | Ядро                   |
| `hypn0/halftone/templates/halftone/index.html`          | Главная                |
| `hypn0/halftone/management/commands/cleanup_temp.py`    | Очистка temp (14 дней) |
| `hypn0/halftone/management/commands/cleanup_reports.py` | Очистка по жалобам     |
| `public/static/css/site.css`                            | Стили                  |
| `public/static/js/site.js`                              | JS                     |
| `.env.sample`                                           | Env template           |
| `Dockerfile`                                            | Сборка                 |
| `docker-compose.local.yml`                              | Dev                    |
| `docker-compose.prod.yml`                               | Prod                   |
| `config/nginx/hypn0-app--external-nginx.conf`           | Nginx                  |
| `.gitea/workflows/docker-publish.yaml`                  | CI/CD                  |
| `database/.gitignore`                                   | Игнор БД               |

## Файлы для модификации

1. `pyproject.toml` — новые зависимости
2. `poetry.lock` — после `poetry lock`

## Файлы для удаления

1. `main.py` — CLI заменён микросайтом

## Верификация

1. `docker compose -f docker-compose.local.yml up` → сайт открывается
2. Загрузка картинки → параметризация → генерация SVG через HTMX
3. SVG отображается в preview с анимацией
4. Скачивание SVG работает
5. `docker compose -f docker-compose.prod.yml` → prod деплой работает
6. CI/CD: тег `v0.1.0` → сборка образа → push

## Производительность: 1 CPU / 1 GB RAM / 10 GB disk

**Storage:**
- Один SVG: ~50–200 КБ (зависит от cols/max_radius)
- 500 публичных SVG в день × 14 дней = ~700 МБ
- 10 ГБ — более чем достаточно (галерея + кэш + ОС)

**CPU:**
- Генерация SVG: Pillow + цикл по пикселям (~6400 точек при cols=80)
- Python: ~0.1–0.5 сек на генерацию
- Gunicorn: 2–4 воркера → ~10–30 req/min на генерацию
- Просмотры галереи: Nginx раздает статику напрямую (минимум нагрузки)

**Трафик:**
- 100–200 пользователей/день на генерацию — без проблем
- Сотни просмотров галереи — без проблем
- 500+ генераций/день → вертикальное масштабирование (2 CPU / 2 GB)

## Долгосрочный Roadmap / Отдаленные TODO (Post-MVP)

### 1. Оптимизация веса SVG через 4-символьную HEX-палитру (`#RGB`)
- **Цель:** Максимальная компактность генерируемого SVG и инлайновых стилей/анимаций.
- **Идея:** Ограничить цветовую палитру короткими 4-символьными HEX-кодами (`#RGB`, например `#CD0`, `#F00`, `#08F` — всего $16^3 = 4096$ цветов или квантованная выборка из 256 цветов).
- **Эффект:** Экономия до 3–4 байт на каждом элементе/переменной цвета в SVG, что при тысячах точек дает существенное уменьшение веса итогового файла.
- **UI/Фронтенд:**
  - Реализация компактного интерфейса выбора из ограниченной палитры без раздувания HTML-кода (через динамический генератор палитры на Alpine.js, цветовую сетку с шагом оттенков или компактный модал/попап).
  - Округление/квантование цвета на клиенте и бэкенде до ближайшего 3-значного hex-значения.
