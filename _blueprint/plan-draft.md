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
│  🧠 HypnoSVG                           [Галерея] [О]  │
├───────────────────┬───────────────────────────────────┤
│  ◀ Настройки      │  ▶ Превью                         │
│                   │                                   │
│  ┌──────────────┐ │  ┌─────────────────────────────┐  │
│  │ 📷 Загрузить │ │  │   <svg viewBox="...">       │  │
│  └──────────────┘ │  │     <style>...</style>      │  │
│                   │  │   </svg>                    │  │
│  ─── Стиль ─────  │  │                             │  │
│  ┌─┐┌─┐┌─┐┌─┐     │  │  [♥ liked] [Скачать]        │  │
│  │●│┌─┐┌─┐┌─┐     │  └─────────────────────────────┘  │
│  └─┘└─┘└─┘└─┘     │  [Поделиться] 🔗                  │
│  circle           │                                   │
│                   │                                   │
│  ─── Сетка ─────  │                                   │
│  ┌─┐┌─┐┌─┐┌─┐     │                                   │
│  │●│┌─┐┌─┐┌─┐     │                                   │
│  └─┘└─┘└─┘└─┘     │                                   │
│  grid             │                                   │
│                   │                                   │
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
│  [thumb]   [thumb]   [thumb]   [thumb] ...            │
│  [♥ 12]    [♥ 8]     [♥ 23]    [♥ 5]                  │
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

**CSS:**
- Dev: Tailwind CDN (`<script src="https://cdn.tailwindcss.com"></script>`) + Purge content в конфиге
- Prod: `collectstatic` → `whitenoise` обслуживает скомпилированную статику

HTMX: форма с `hx-post`, `hx-encoding="multipart/form-data"` → SVG вставляется в `#preview`.

### 4. Политика хранения

**Исходные изображения:** удаляются сразу после генерации (не хранятся вообще).

**Публичные SVG (опционально, по желанию пользователя):**
```
public/media/temp/{hash_16символов}.svg
```
- TTL: **14 дней**
- URL: `/view/{hash}` — прямая ссылка, без индексации
- Автоматическая очистка: `manage.py cleanup_temp --older-than 1209600` → crontab

**Галерея (FeaturedSVG):**
- Администратор/promote: лучшие SVG переезжают из `temp/` в `gallery/`
- Хранятся вечно (лучшая коллекция халфтонов)
- Прямая ссылка: `/gallery/{hash}`
- `/gallery` — страница галереи со всеми (пагинация)

**Модель `FeaturedSVG`:**
```python
class FeaturedSVG(models.Model):
    svg_hash = models.CharField(max_length=16, unique=True)
    original_temp_path = models.CharField(max_length=512)
    gallery_path = models.CharField(max_length=512)
    params_json = models.JSONField(default=dict)
    votes = models.PositiveIntegerField(default=0)
    promoted_at = models.DateTimeField(auto_now_add=True)
    promoted_by = models.ForeignKey('auth.User', null=True, blank=True)
    reports_count = models.PositiveIntegerField(default=0)
```

**Report / жалоба:**
- `/report/{hash}` — кнопка "Пожаловаться" на странице просмотра
- Просто счётчик `reports_count` в модели (или просто scan для ручного удаления)
- После жалобы — админ проверяет и удаляет вручную

**Публичный режим:**
Все генерации публичны:
- Любой SVG доступен к скачиванию
- SVG показываются в браузере по `temp/` или `/gallery`, но доступны только `/hypn0/` с hash-именем
- В браузере, показывается "Поделиться ссылкой"

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
