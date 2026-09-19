# frontend-assembly

Эта папка отвечает за сборку всех фронтенд-зависимостей проекта HYPN0.
Каждый подкаталог — отдельный инструмент, который собирается в готовый бандл/статик.

## Что здесь лежит

### `tailwind/` — сборка Tailwind CSS v4

```
tailwind/
├── package.json          # Зависимости: @tailwindcss/cli, tailwindcss v4
├── package-lock.json     # Фиксация версий
└── build-tailwind.sh     # ← запускается из корня проекта (scripts/build-tailwind.sh)
```

**Что делает:**
- `build-tailwind.sh` создаёт временный `input.css` с директивами `@import "tailwindcss";`, `@source` и импортом `tailwind-custom.css`,
  запускает `npm install` + `npm run build` (`@tailwindcss/cli`), собирает `public/static/css/tailwind.min.css`,
  затем удаляет временные файлы.
- Результат: `public/static/css/tailwind.min.css` — минифицированный CSS со всеми
  используемыми утилитами + кастомные стили из `hypn0/templates/css/tailwind-custom.css`.

### `htmx/` — сборка htmx

```
htmx/
├── package.json
└── package-lock.json
```

### `alpine/` — сборка Alpine.js

```
alpine/
├── package.json
└── package-lock.json
```

### `codemirror/` — сборка CodeMirror 6 для админки Django

```
codemirror/
├── package.json          # Зависимости: @codemirror/*, esbuild, @uiw/codemirror-theme-solarized
└── package-lock.json     # Фиксация версий
```

**Что делает:**
- `build-codemirror.sh` генерирует точку входа `src/editor.js` с поддержкой языков (HTML, CSS, JavaScript, JSON), автоматической смены темы (Solarized Light / Dark), форматирования и двусторонней синхронизации с Django админкой (`textarea[data-codemirror-editor]`).
- Собирает единый минифицированный IIFE-бандл через `esbuild` в `public/static/codemirror/editor.js`.

## Как запускать сборки

Из корня проекта:

```bash
# Tailwind CSS
bash scripts/build-tailwind.sh

# htmx
bash scripts/build-htmx.sh

# Alpine.js
bash scripts/build-alpine.sh

# CodeMirror 6 (для админки Django)
bash scripts/build-codemirror.sh
```

Каждый скрипт сам делает всё:
1. проверяет наличие `npm`;
2. создаёт временные файлы;
3. устанавливает зависимости через `npm ci` (или `npm install`);
4. запускает `npm run build`;
5. кладёт готовый бандл в `public/static/...`;
6. удаляет временные файлы.

В рабочем дереве не остаётся мусора от сборки.
