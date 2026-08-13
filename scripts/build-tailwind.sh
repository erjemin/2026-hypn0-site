#!/usr/bin/env bash
# Сборка Tailwind CSS v3 для фронтенда HYPN0
# Запуск из корня проекта: bash ./scripts/build-tailwind.sh

set -euo pipefail

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
# Все рабочие файлы (postcss.config.js, tailwind.config.js, input.css)
# создаются здесь и удаляются в EXIT/INT/TERM.
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

if [[ ! -f "$TAILWIND_DIR/package-lock.json" ]]; then
  fail "Не найден package-lock.json: $TAILWIND_DIR/package-lock.json"
fi

mkdir -p "$OUTPUT_DIR"

# --- tailwind.config.js ---
log "Создаю tailwind.config.js"
cat > "$TAILWIND_DIR/tailwind.config.js" <<'TWEOF'
/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    '../../hypn0/templates/**/*.html',
    '../../hypn0/hypn0_site/**/*.py',
  ],
  theme: {
    extend: {},
  },
  plugins: [],
}
TWEOF

# --- postcss.config.js ---
log "Создаю postcss.config.js"
cat > "$TAILWIND_DIR/postcss.config.js" <<'PCEOF'
module.exports = {
  plugins: {
    tailwindcss: {},
    autoprefixer: {},
  },
}
PCEOF

# --- input.css ---
log "Создаю input.css"
cat > "$TAILWIND_DIR/input.css" <<'EOF'
/*
  input.css — точка входа для сборки prod-версии Tailwind CSS v3.

  Собирается через `npm run build` (PostCSS) в
  файл public/static/css/tailwind.min.css, который подключается в _base.html
  для production (когда settings.DEBUG == False).

  Здесь же подключаются кастомные стили из hypn0/templates/css/tailwind-custom.css —
  того же самого файла, который в dev-режиме подключается через {% include %} внутрь
  инлайнового <style type="text/tailwindcss"> в _base.html.

  Это обеспечивает единый источник кастомных стилей для dev и prod.
*/
@tailwind base;
@tailwind components;
@tailwind utilities;

@import "../../hypn0/templates/css/tailwind-custom.css";
EOF

log "СОБИРАЮ Tailwind CSS v3"
cd "$TAILWIND_DIR"

log 'Устанавливаю зависимости через npm ci'
npm ci

log 'Собираю CSS'
npm run build

log 'ГОТОВО! Результат: '"$OUTPUT_DIR/tailwind.min.css"
