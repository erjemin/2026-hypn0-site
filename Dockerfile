# =================================================
# STAGE 1: Builder - Установка зависимостей
# =================================================
FROM python:3.14-slim AS builder

# Устанавливаем переменные окружения
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PIP_DEFAULT_TIMEOUT=100

# ENV POETRY_VERSION=2.1.1
# ENV POETRY_HOME="/opt/poetry"
# ENV POETRY_NO_INTERACTION=1
# ENV POETRY_VIRTUALENVS_IN_PROJECT=true

# Устанавливаем Poetry
RUN pip install --no-cache-dir --default-timeout=100 --retries 10 poetry poetry-plugin-export

# Создаем рабочую директорию
WORKDIR /app

# Копируем только файлы зависимостей для кэширования этого слоя
COPY pyproject.toml poetry.lock /app/

# Экспортируем lock-файл в requirements.txt и ставим зависимости через pip.
# Это обычно быстрее и проще для Docker, чем полноценная установка через Poetry.
RUN poetry export --format requirements.txt --without-hashes --with dev --output /tmp/requirements.txt \
    && pip install --no-cache-dir --default-timeout=100 --retries 10 -r /tmp/requirements.txt


# =================================================
# STAGE 2: Final - Создание чистого и безопасного образа
# =================================================
FROM python:3.14-slim AS stage-final

# Устанавливаем переменные окружения
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV DJANGO_SETTINGS_MODULE=hypn0.settings
ENV PYTHONPATH="/home/app/web/hypn0"
ENV HOME="/home/app"


# Создаем пользователя без прав root для безопасности
# RUN addgroup --system app && adduser --system --ingroup app app

# Создаем рабочую директорию
WORKDIR /home/app/web

# Копируем установленные Python-пакеты из builder-стадии
# Каталог /usr/local/bin нужен для бинарных файлов, таких как gunicorn, pytest, whitenoise и т.п.
COPY --from=builder /usr/local/bin /usr/local/bin
#Каталог /usr/local/lib/python3.14/site-packages нужен для обычных Python-пакетов и батареек
COPY --from=builder /usr/local/lib/python3.14/site-packages /usr/local/lib/python3.14/site-packages

# Копируем исходный код проекта и устанавливаем правильного владельца
# ИЗМЕНЕНИЕ: app:app -> 1000:1000
COPY --chown=1000:1000 . .

# 1. Создаём директорию для конфигов nginx и даём права пользователю app
#    Это выполняется ещё от root, поэтому проблем с permissions не будет.
# 2. Создаём директорию для собранной статики и даём права пользователю app.
#    `STATIC_ROOT` в settings.py живёт внутри `public`.
# 3. Создаём директорию для ошибок (404, 500) и даём права пользователю app
# 4. Создаём директорию для БД и даём права пользователю app
#    Это важно когда БД монтируется как том с хоста
RUN mkdir -p /home/app \
             /nginx_configs_host/nginx \
             /home/app/web/public/staticfiles \
             /home/app/web/public/media/_error \
             /home/app/web/database && \
    chown -R 1000:1000 /nginx_configs_host /home/app/web/public /home/app/web/database

# Переключаемся на пользователя без прав root
USER 1000


# Собираем статику
# Используем dummy ключ, так как .env файла нет на этапе сборки
RUN SECRET_KEY=dummy python hypn0/manage.py collectstatic --noinput --clear

# Открываем порт
EXPOSE 8000

# Проверка здоровья контейнера
# Docker будет периодически проверять, жив ли контейнер, отправляя GET запрос к главной странице.
# Параметры:
#   --interval=30s    - проверка каждые 30 секунд
#   --timeout=3s      - ожидаем ответ максимум 3 секунды
#   --start-period=10s - даем контейнеру 10 секунд на запуск перед первой проверкой
#   --retries=3       - объявляем контейнер unhealthy после 3 неудачных попыток
HEALTHCHECK --interval=30s --timeout=3s --start-period=10s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/').read()" || exit 1

# Переходим в директорию с manage.py для корректного запуска gunicorn
WORKDIR /home/app/web/hypn0

# Команда запуска (два воркера для лучшей производительности, можно увеличить до число ядер на хосте)
CMD ["python", "-m", "gunicorn", "--workers", "2", "--bind", "0.0.0.0:8000", "hypn0.wsgi:application"]
