# frontend-assembly

Эта папка отвечает за сборку всех фронтенд-зависимостей проекта HYPN0.
Каждый подкаталог — отдельный инструмент, который собирается в готовый бандл/статик.

## Что здесь лежит

### `tailwind/` — сборка Tailwind CSS v3.4

```
tailwind/
├── package.json          # Зависимости: tailwindcss@3.4, postcss, autoprefixer
├── package-lock.json     # Фиксация версий
└── build-tailwind.sh     # ← запускается из корня проекта
```

**Что делает:**
- `build-tailwind.sh` создаёт временные файлы (`tailwind.config.js`, `postcss.config.js`, `input.css`),
  запускает `npm ci` + `npm run build`, собирает `public/static/css/tailwind.min.css`,
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

## Как запускать сборки

Из корня проекта:

```bash
# Tailwind CSS
bash scripts/build-tailwind.sh

# htmx
bash scripts/build-htmx.sh

# Alpine.js
bash scripts/build-alpine.sh
```

Каждый скрипт сам делает всё:
1. проверяет наличие `npm`;
2. создаёт временные файлы;
3. устанавливает зависимости через `npm ci`;
4. запускает `npm run build`;
5. кладёт готовый бандл в `public/static/...`;
6. удаляет временные файлы.

В рабочем дереве не остаётся мусора от сборки.

## Кодовая статика

В будущем — возможно, сборка CodeMirror 6 для админки Django.
