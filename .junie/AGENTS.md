# Сведения для разработчиков (AGENTS.md)

Проект **HypnoSVG** — микросайт на Django для генерации анимированных SVG-халфтонов.

### Стек технологий
- **Backend:** Django 6.0.8+, Python 3.14+
- **Frontend:** HTMX (интерактивность), Alpine.js (клиентская логика), Tailwind CSS 4 (CDN в dev, v3 в prod — в процессе перехода).
- **Графика:** Pillow (обработка), в планах scikit-learn (k-means) и numpy.
- **Инфраструктура:** Poetry (зависимости), Whitenoise (статика в prod), Gunicorn.

### Архитектура и структура
- **Корневые папки:**
  - `hypn0/`: Исходный код Django (проект и основное приложение `hypn0_site`).
  - `public/`: Публичная статика и медиа-файлы (разделено для dev/prod).
  - `database/`: Файлы БД SQLite (вынесены из корня приложения).
  - `frontend-assembly/`: Исходники для сборки фронтенд-библиотек.
  - `scripts/`: Скрипты автоматизации сборки фронтенда.
- **Django настройки:**
  - `ADMIN_URL`: Настраивается через `.env`, по умолчанию скрыт.
  - `context_processors.py`: Предоставляет `IS_DEBUG` и `ALLOW_TRACKING` (GDPR-friendly cookie consent).
  - `urls.py`: В режиме `DEBUG` автоматически пробрасывает файлы из корня `public` (favicon, robots.txt и др.).
- **Кастомные стили:**
  - `hypn0/templates/css/tailwind-custom.css` — основной файл стилей (директивы Tailwind 4). Подключается инлайново через `include` в `_base.html` (dev) и импортируется в `input.css` (prod).

### Сборка фронтенда
Фронтенд-зависимости не лежат в репозитории как готовые бандлы. Для их обновления используйте скрипты из корня:
- `bash scripts/build-tailwind.sh` (Внимание: скрипт требует обновления до v4 для полной совместимости с `tailwind-custom.css`).
- `bash scripts/build-htmx.sh`
- `bash scripts/build-alpine.sh`
Скрипты используют `npm ci` во временных папках внутри `frontend-assembly/` и копируют результат в `public/static/`.

### Ядро генерации (Plan)
Основная логика переносится из CLI-прототипа в `hypn0_site/services/halftone.py`.
- Вход: `PIL.Image`.
- Выход: Строка SVG с инлайновыми CSS-анимациями.
- Основные параметры: `cols` (плотность сетки), `max_radius`, цветовые схемы.

### Важные нюансы
- **Static & Media:** В `settings.py` пути настроены так, чтобы `public` была общей точкой входа для Nginx.
- **Database:** Используется WAL-режим для SQLite (настраивается в `settings.py` через сигнал `connection_created`).
- **Templates:** Базовый шаблон `_base.html` содержит логику подключения HTMX/Alpine и модалку согласия на трекинг.

### Стиль кода
- **Python:** PEP8, Black, isort. Отступы 4 пробела, max line length 180-200.
- **HTML:** Django templates, Tailwind CSS классы в BEM. Отступы 2 пробела, max line length 250.
- Комментарии в коде на русском, переменные и функции на английском.
- Избегать emojis в коде, комментариях и инструкциях. Сленг и токсичные выражения допускаются.
- В интерфейсе и для пользователей текст в стиле "Гипножаба контролирует ваши действия" (игра слов, юмор, мемы).