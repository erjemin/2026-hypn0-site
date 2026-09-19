#!/usr/bin/env bash
# Сборка Tailwind CSS v4 для фронтенда HYPN0
# Запуск из корня проекта: bash ./scripts/build-tailwind.sh

set -euo pipefail

export PATH="/opt/homebrew/bin:/usr/local/bin:$PATH"

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TAILWIND_DIR="$PROJECT_ROOT/frontend-assembly/tailwind"
OUTPUT_DIR="$PROJECT_ROOT/public/static/css"

log() {
  printf '[tailwind] %s\n' "$*"
}

fail() {
  printf '[tailwind] %s\n' "$*" >&2
  exit 1
}

# cleanup() — удаляет временные файлы при любом завершении скрипта.
cleanup() {
  rm -rf "$TAILWIND_DIR/node_modules" \
         "$TAILWIND_DIR/postcss.config.js" \
         "$TAILWIND_DIR/tailwind.config.js" \
         "$TAILWIND_DIR/input.css"
}

trap cleanup EXIT INT TERM

if ! command -v npm >/dev/null 2>&1; then
  fail 'Не найден `npm`. Установи Node.js и повтори сборку.'
fi

if [[ ! -f "$TAILWIND_DIR/package.json" ]]; then
  fail "Не найден package.json: $TAILWIND_DIR/package.json"
fi

mkdir -p "$OUTPUT_DIR"

# --- input.css ---
log "Создаю input.css для Tailwind v4"
cat > "$TAILWIND_DIR/input.css" <<'EOF'
/*
  input.css — точка входа для сборки prod-версии Tailwind CSS v4.

  Собирается через @tailwindcss/cli в
  файл public/static/css/tailwind.min.css, который подключается в _base.html
  для production (когда settings.DEBUG == False).

  Здесь же подключаются кастомные стили из hypn0/templates/css/tailwind-custom.css.
*/
@import "tailwindcss";

@source "../../hypn0/templates";
@source "../../hypn0/hypn0_site";

@import "../../hypn0/templates/css/tailwind-custom.css";
EOF

log "СОБИРАЮ Tailwind CSS v4"
cd "$TAILWIND_DIR"

# Если package-lock.json отсутствует или устарел, используем npm install / npm ci
if [[ -f "$TAILWIND_DIR/package-lock.json" ]]; then
  log 'Устанавливаю зависимости через npm install'
  npm install --no-audit --no-fund
else
  log 'Устанавливаю зависимости через npm install'
  npm install --no-audit --no-fund
fi

log 'Собираю CSS'
npm run build

log 'ГОТОВО! Результат: '"$OUTPUT_DIR/tailwind.min.css"
