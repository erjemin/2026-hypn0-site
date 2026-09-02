import io
import math
import random
import re
from collections import defaultdict
from typing import BinaryIO, Union

from PIL import Image


def encode_to_base36(num: int) -> str:
    """Кодирует неотрицательное число в компактный строковый идентификатор."""
    if num < 0:
        raise ValueError("Число должно быть неотрицательным")

    charset = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"
    if num < len(charset):
        return charset[num]

    result = []
    while num > 0:
        result.append(charset[num % len(charset)])
        num //= len(charset)
    return "".join(reversed(result))


def generate_shape_def(shape: str, radius: int, shape_id: str) -> str:
    """Генерирует SVG-элемент для тега <defs> в зависимости от типа фигуры."""
    r = radius
    match shape:
        case "ring":
            stroke_width = max(1.0, r * 0.35)
            inner_r = max(0.5, r - stroke_width / 2.0)
            return f'<circle id="{shape_id}" r="{inner_r:.1f}" fill="none" stroke="currentColor" stroke-width="{stroke_width:.1f}"/>'

        case "square":
            size = r * 2
            rx = max(0.5, r * 0.1)
            return f'<rect id="{shape_id}" class="shape" x="{-r}" y="{-r}" width="{size}" height="{size}" rx="{rx:.1f}"/>'

        case "diamond":
            return f'<polygon id="{shape_id}" class="shape" points="0,{-r} {-r},0 0,{r} {r},0"/>'

        case "triangle":
            return f'<polygon id="{shape_id}" class="shape" points="0,{-r} {-r},{r} {r},{r}"/>'

        case "hexagon":
            w = round(r * 0.866)
            h_half = round(r * 0.5)
            return f'<polygon id="{shape_id}" class="shape" points="0,{-r} {w},{-h_half} {w},{h_half} 0,{r} {-w},{h_half} {-w},{-h_half}"/>'

        case "star":
            points = []
            inner_r = r * 0.45
            for i in range(10):
                angle = i * math.pi / 5 - math.pi / 2
                curr_r = r if i % 2 == 0 else inner_r
                px = round(curr_r * math.cos(angle), 1)
                py = round(curr_r * math.sin(angle), 1)
                points.append(f"{px},{py}")
            pts_str = " ".join(points)
            return f'<polygon id="{shape_id}" class="shape" points="{pts_str}"/>'

        case "cross":
            arm = max(1, round(r * 0.35))
            return f'<path id="{shape_id}" class="shape" d="M{-arm},{-r} H{arm} V{-arm} H{r} V{arm} H{arm} V{r} H{-arm} V{arm} H{-r} V{-arm} H{-arm} Z"/>'

        case "line":
            th = max(1, round(r * 0.25))
            return f'<rect id="{shape_id}" class="shape" x="{-r}" y="{-th}" width="{2*r}" height="{2*th}" rx="1"/>'

        case "wave":
            th = max(1.0, r * 0.3)
            return f'<path id="{shape_id}" class="shape" d="M{-r},0 Q{-r/2:.1f},{-r} 0,0 T{r},0" fill="none" stroke="currentColor" stroke-width="{th:.1f}"/>'

        case "heart":
            scale_f = r / 12.0
            return (
                f'<path id="{shape_id}" class="shape" transform="scale({scale_f:.3f}) translate(-12, -12)" '
                f'd="M12 21.35l-1.45-1.32C5.4 15.36 2 12.28 2 8.5 2 5.42 4.42 3 7.5 3c1.74 0 3.41.81 4.5 2.09C13.09 3.81 14.76 3 16.5 3 19.58 3 22 5.42 22 8.5c0 3.78-3.4 6.86-8.55 11.54L12 21.35z"/>'
            )

        case "circle" | _:
            return f'<circle id="{shape_id}" class="shape" r="{r}"/>'


def generate_halftone_svg(
    image: Union[Image.Image, BinaryIO, bytes, str],
    *,
    cols: int = 35,
    max_radius: int = 8,
    shape: str = "circle",
    color: str = "#a855ff",
    opacity: float = 0.9,
    blink: int = 6,
    rotation: int = 0,
    scale: int = 980,
    angle: int = 0,
    animation_variants: int = 12,
    seed: int = 42,
) -> str:
    """
    Генерирует чистый оптимизированный SVG-халфтон из растрового изображения.

    Параметры:
    - image: PIL Image, файловый объект (BytesIO), байты или путь к файлу
    - cols: число точек по наибольшей стороне сетки (10-200)
    - max_radius: максимальный радиус/размер точки (3-20)
    - shape: тип фигуры ('circle', 'ring', 'square', 'diamond', 'triangle', 'hexagon', 'star', 'cross', 'line', 'wave', 'heart')
    - color: основной HEX цвет (например '#a855ff')
    - opacity: коэффициент непрозрачности (0.0 - 1.0)
    - blink: интенсивность мерцания (0 - выключено/статичный, 1-10 - скорость)
    - rotation: угол покачивания в градусах (-15 .. +15)
    - scale: масштаб пульсации (800 .. 1040, где 980 = 0.98)
    - angle: наклон растровой сетки (-44 .. +45)
    - animation_variants: число вариантов CSS-задержек
    - seed: сид для детерминированного распределения анимаций

    TODO ПОЧИНИТЬ-УЛУЧШИТЬ:
    - max_radius (радиус точки): сейчас зазор между точками не меняется. Нужно чтобы:
        - при d=0 -- зазор 10
        - при d<10 -- зазор 10-d
        - при d>10 -- перекрытие d-10 (отрицательный зазор)
    - angle: сейчас это просто поворот картинки. Нужно чтобы:
        - нужно чтобы это был поворт картинки (т.е. ряды-столбцы были со смещение-поворотом, как при полиграфии)
    - blink: что-то страннное. пока не понял

    -- ЦВЕТА: ЕСЛИ ЦВЕТ ЧЕРЕЗ ИНТЕРФЕЙС НЕ МЕНЯЛСЯ (ДЕФОЛТНФЫЙ), ТО НАЗНАЧАТЬ СЛУАНЫЙ. А то слишком однообразные цвета
    """
    rng = random.Random(seed)

    # 1. Загрузка и подготовка изображения в градациях серого
    if isinstance(image, (bytes, bytearray)):
        pil_img = Image.open(io.BytesIO(image))
    elif hasattr(image, "read"):
        if hasattr(image, "seek"):
            image.seek(0)
        pil_img = Image.open(image)
    elif isinstance(image, str):
        pil_img = Image.open(image)
    elif isinstance(image, Image.Image):
        pil_img = image
    else:
        raise ValueError("Неподдерживаемый тип входного изображения")

    # Конвертируем в Grayscale
    img = pil_img.convert("L")

    # Обработка наклона сетки (angle): поворачиваем изображение при необходимости
    if angle != 0:
        # Поворачиваем с сохранением пропорций и белым фоном (255 = прозрачно/пусто)
        img = img.rotate(-angle, resample=Image.Resampling.BICUBIC, expand=True, fillcolor=255)

    # Вычисляем размеры сетки: значение `cols` задает число точек по наибольшей стороне (ширине или высоте)
    if img.width >= img.height:
        grid_width = max(1, cols)
        grid_height = max(1, round(cols * (img.height / img.width)))
    else:
        grid_height = max(1, cols)
        grid_width = max(1, round(cols * (img.width / img.height)))

    img_resized = img.resize((grid_width, grid_height), Image.Resampling.LANCZOS)

    step = max_radius * 2 + 2
    width = grid_width * step
    height = grid_height * step

    # 2. Формирование классов анимации
    animation_classes = []
    is_animated = blink > 0

    # Длительность цикла анимации: при blink=10 -> 0.6s, при blink=1 -> 2.4s
    duration = max(0.4, 2.5 - (blink * 0.19)) if is_animated else 1.0

    for i in range(animation_variants):
        delay = (i / animation_variants) * duration * 1.5
        encoded_i = encode_to_base36(i)
        delay_str = f"{int(delay)}" if delay == int(delay) else f"{delay:.2f}".rstrip("0").rstrip(".")
        animation_classes.append(f".a{encoded_i}{{--d:{delay_str}s}}")

    # 3. Обход пикселей и группировка
    elements_by_class = defaultdict(list)
    unique_radii = set()

    for y in range(grid_height):
        for x in range(grid_width):
            brightness = img_resized.getpixel((x, y))
            factor = (255 - brightness) / 255.0

            # Отсекаем слишком светлые участки (шум фона)
            if factor < 0.12:
                continue

            radius = int(factor * max_radius)
            if radius == 0:
                continue

            cx = x * step + step // 2
            cy = y * step + step // 2

            anim_class = rng.randint(0, animation_variants - 1)
            encoded_class = encode_to_base36(anim_class)

            elements_by_class[encoded_class].append((radius, cx, cy))
            unique_radii.add(radius)

    # 4. Формирование <defs>
    defs_list = ["<defs>"]
    for radius in sorted(unique_radii):
        shape_id = f"s{encode_to_base36(radius)}"
        defs_list.append(generate_shape_def(shape, radius, shape_id))
    defs_list.append("</defs>")
    defs_html = "".join(defs_list)

    # 5. Формирование групп <g class="a...">
    groups = []
    for anim_class in sorted(elements_by_class.keys()):
        group_elements = elements_by_class[anim_class]
        uses = "".join(
            f'<use href="#s{encode_to_base36(radius)}" x="{cx}" y="{cy}"/>'
            for radius, cx, cy in group_elements
        )
        if uses:
            groups.append(f'<g class="a{anim_class}">{uses}</g>')

    animation_css = "".join(animation_classes)
    groups_html = "".join(groups)

    # 6. Стилизация и Keyframes
    scale_val = max(0.5, min(1.5, scale / 1000.0))
    scale_str = f"{scale_val:.3f}".rstrip("0").rstrip(".")
    rot_str = f"{rotation}deg"

    # Корректный цвет с прозрачностью
    clean_color = color.strip() if color else "#a855ff"
    if not clean_color.startswith("#"):
        clean_color = f"#{clean_color}"

    # Добавляем альфа-канал в hex при необходимости или используем CSS opacity
    fill_style = f"fill:{clean_color};stroke:{clean_color};opacity:{opacity:.2f};"

    if is_animated:
        # Управление паузой/запуском через CSS Custom Property --hypn0-play.
        # По умолчанию running (для живого превью и детального просмотра).
        # В галерее значение переопределяется на paused для 0% нагрузки на процессор.
        anim_rule = (
            f"animation:noise {duration:.2f}s ease-in-out infinite alternate;"
            f"animation-delay:var(--d);"
            f"animation-play-state:var(--hypn0-play,running);"
        )
        keyframes_rule = (
            f"@keyframes noise{{"
            f"0%{{opacity:{max(0.2, opacity * 0.7):.2f};transform:scale(1) rotate(0deg)}}"
            f"50%{{opacity:{opacity:.2f}}}"
            f"100%{{opacity:{max(0.1, opacity * 0.5):.2f};transform:scale({scale_str}) rotate({rot_str})}}"
            f"}}"
        )
    else:
        anim_rule = "animation:none;"
        keyframes_rule = ""

    svg_css = (
        f"<style>"
        f"svg{{background:transparent}}"
        f".shape,circle,rect,polygon,path{{{fill_style}transform-origin:center;{anim_rule}transition:all .5s ease-out}}"
        f"{keyframes_rule}"
        f".frozen .shape,.frozen circle,.frozen rect,.frozen polygon,.frozen path{{animation:none!important;opacity:{opacity:.2f}!important;transform:none!important}}"
        f"{animation_css}"
        f"</style>"
    )

    svg_template = (
        f'<!-- Generated by Hypn0 Generator (https://hypn0.ru) -->\n'
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" width="100%" height="100%">'
        f'{svg_css}'
        f'{defs_html}'
        f'<g id="hypn0-canvas">{groups_html}</g>'
        f'</svg>'
    )

    return svg_template


def prepare_gallery_svg(svg_content: str) -> str:
    """
    Модифицирует SVG для долговременного хранения в галерее:
    внедряет CSS Custom Property (--hypn0-play: paused), которое свободно наследуется
    внутрь элементов и теневых деревьев <use>.

    Логика работы:
    1. В покое (--hypn0-play: paused): 0% потребления CPU и GPU браузера в ленте галереи.
    2. При наведении курсора (:host(:hover) в Shadow DOM или svg:hover при открытии файла):
       значение переключается на running, и анимация оживает.
    """
    if not svg_content:
        return svg_content

    # Наследуемая переменная паузы и оверрайд стилей фигур
    # Важно: селектор :host(:hover) работает при вставке в Shadow DOM карточки,
    # а svg:hover работает, если файл открыт напрямую в браузере.
    hover_css = (
        "svg{--hypn0-play:paused}"
        ":host(:hover) svg,svg:hover{--hypn0-play:running!important}"
        ".shape,circle,rect,polygon,path{animation-play-state:var(--hypn0-play,paused)!important}"
    )

    if "</style>" in svg_content:
        return svg_content.replace("</style>", f"{hover_css}</style>", 1)

    return svg_content


def prepare_active_svg(svg_content: str) -> str:
    """
    Возвращает полностью активный SVG без паузы анимации вне ховера
    для страницы детального просмотра (/gallery/<hash_id>) и скачивания пользователем.

    Удаляет оверрайды пауз (--hypn0-play: paused), восстанавливая оригинальные
    авторские цвета, прозрачности и непрерывную живую анимацию на полной мощности.
    """
    if not svg_content:
        return svg_content

    # Удаляем внедренные правила паузы через CSS-переменные и старые форматы
    gallery_css_variants = [
        "svg{--hypn0-play:paused}:host(:hover) svg,svg:hover{--hypn0-play:running!important}.shape,circle,rect,polygon,path{animation-play-state:var(--hypn0-play,paused)!important}",
        "svg{--hypn0-play:paused}svg:hover{--hypn0-play:running}.shape,circle,rect,polygon,path{animation-play-state:var(--hypn0-play,paused)!important}",
    ]
    cleaned = svg_content
    for gcss in gallery_css_variants:
        cleaned = cleaned.replace(gcss, "")

    cleaned = re.sub(r"svg\s*\{[^}]*--hypn0-play:\s*paused[^}]*\}", "", cleaned)
    cleaned = re.sub(r"(:host\(:hover\)\s*svg\s*,\s*)?svg:hover\s*\{[^}]*--hypn0-play:[^}]*\}", "", cleaned)
    cleaned = re.sub(
        r"\.shape,circle,rect,polygon,path\s*\{animation-play-state:\s*var\(--hypn0-play,\s*paused\)!important\}",
        "",
        cleaned,
    )
    cleaned = re.sub(r"@media\s*\(\s*hover\s*:\s*hover\s*\)\s*\{[^}]*:[^}]*\}", "", cleaned)
    cleaned = re.sub(r"svg:not\(:hover\)[^{]*\{[^}]*\}", "", cleaned)
    old_hover_css = (
        "svg:not(:hover) .shape,svg:not(:hover) circle,svg:not(:hover) rect,"
        "svg:not(:hover) polygon,svg:not(:hover) path{animation-play-state:paused!important}"
    )
    cleaned = cleaned.replace(old_hover_css, "")
    return cleaned


def analyze_svg_structure(svg_content: str) -> dict:
    """
    Анализирует разметку SVG и возвращает наукообразную детальную статистику
    по геометрическим примитивам, классам, анимациям и энтропии данных.
    """
    if not svg_content:
        return {
            "total_bytes": 0,
            "total_kb": 0.0,
            "total_oscillators": 0,
            "use_count": 0,
            "circle_count": 0,
            "rect_count": 0,
            "polygon_count": 0,
            "path_count": 0,
            "defs_count": 0,
            "groups_count": 0,
            "keyframes_count": 0,
            "classes_count": 0,
            "viewbox": "0 0 1000 1000",
            "width": 1000,
            "height": 1000,
            "aspect_ratio": "1:1",
            "density": 0.0,
            "bytes_per_quantum": 0.0,
        }

    total_bytes = len(svg_content.encode("utf-8"))

    # Подсчет векторных сущностей
    use_count = len(re.findall(r"<use\b", svg_content))
    circle_count = len(re.findall(r"<circle\b", svg_content))
    rect_count = len(re.findall(r"<rect\b", svg_content))
    polygon_count = len(re.findall(r"<polygon\b", svg_content))
    path_count = len(re.findall(r"<path\b", svg_content))
    defs_count = circle_count + rect_count + polygon_count + path_count

    # Группы и классы
    groups_count = len(re.findall(r"<g\b", svg_content))
    keyframes_count = len(re.findall(r"@keyframes\b", svg_content))
    classes = set(re.findall(r"\.([a-zA-Z0-9_-]+)\s*\{", svg_content))
    classes_count = len(classes)

    # ViewBox и геометрия
    vb_match = re.search(r'viewBox=["\']([^"\']+)["\']', svg_content)
    viewbox = vb_match.group(1) if vb_match else "0 0 1000 1000"
    vb_parts = viewbox.split()
    try:
        width = int(float(vb_parts[2])) if len(vb_parts) >= 3 else 1000
        height = int(float(vb_parts[3])) if len(vb_parts) >= 4 else 1000
    except (ValueError, IndexError):
        width, height = 1000, 1000

    gcd_val = math.gcd(width, height)
    aspect_ratio = f"{width // gcd_val}:{height // gcd_val}" if gcd_val > 0 else "1:1"

    # Наукообразные показатели
    total_oscillators = use_count if use_count > 0 else defs_count
    bytes_per_quantum = round(total_bytes / max(total_oscillators, 1), 1)
    density = round(total_oscillators / max((width * height) / 1048576.0, 1.0), 2)

    return {
        "total_bytes": total_bytes,
        "total_kb": round(total_bytes / 1024, 2),
        "total_oscillators": total_oscillators,
        "use_count": use_count,
        "circle_count": circle_count,
        "rect_count": rect_count,
        "polygon_count": polygon_count,
        "path_count": path_count,
        "defs_count": defs_count,
        "groups_count": groups_count,
        "keyframes_count": keyframes_count,
        "classes_count": classes_count,
        "viewbox": viewbox,
        "width": width,
        "height": height,
        "aspect_ratio": aspect_ratio,
        "density": density,
        "bytes_per_quantum": bytes_per_quantum,
    }
