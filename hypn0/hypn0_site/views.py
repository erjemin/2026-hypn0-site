import hashlib
import random

from django.conf import settings
from django.core.files.base import ContentFile
from django.core.paginator import Paginator
from django.http import Http404, HttpRequest, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.csrf import ensure_csrf_cookie
from django.views.decorators.http import require_POST

from .forms import HalftoneGenerateForm
from .models import TbHypn0Item, TbVote
from .services.halftone import (
    analyze_svg_structure,
    generate_halftone_svg,
    prepare_active_svg,
    prepare_gallery_svg,
)
from .services.naming import generate_hypno_title


def get_floor_fresh(limit: int | None = 6, offset: int = 0):
    """
    1-й ЭТАЖ: «Плеск бессознательного» (Инкубатор открытий).
    Выборка: свежие кандидаты и первичный поток (Level.CANDIDATE, Level.LEVEL_1).
    Сортировка: по наименьшему числу просмотров i_views_count (чтобы дать шанс всем) и свежести -d_created_at.
    """
    qs = TbHypn0Item.objects.filter(
        i_level__in=[TbHypn0Item.Level.CANDIDATE, TbHypn0Item.Level.LEVEL_1],
        is_public=True,
    ).order_by("i_views_count", "-d_created_at")

    if limit is not None:
        return qs[offset : offset + limit]
    return qs


def gallery_floor(request: HttpRequest, floor_slug: str) -> HttpResponse:
    """
    Страница полного просмотра конкретного этажа галереи с пагинацией (по 8 карточек).
    """
    floors_config = {
        "fresh": {
            "title": "Плеск бессознательного",
            "badge": "FRESH STREAM",
            "badge_color": "amber",
            "subtitle": "Свежие галлюцинации из инкубатора • Первичная оценка сообщества",
            "getter": get_floor_fresh,
        },
    }

    if floor_slug not in floors_config:
        raise Http404("Этаж транса не обнаружен в матрице")

    cfg = floors_config[floor_slug]
    items_qs = cfg["getter"](limit=None)

    paginator = Paginator(items_qs, 8)
    page_number = request.GET.get("page", 1)
    page_obj = paginator.get_page(page_number)

    context = {
        "floor_slug": floor_slug,
        "floor_title": cfg["title"],
        "floor_badge": cfg["badge"],
        "floor_badge_color": cfg["badge_color"],
        "floor_subtitle": cfg["subtitle"],
        "page_obj": page_obj,
    }
    return render(request, "gallery/floor.html", context)


@ensure_csrf_cookie
def index(request: HttpRequest | None) -> HttpResponse:
    fresh_items = get_floor_fresh(limit=6)
    return render(request, "index.html", {
        "fresh_items": fresh_items,
    })


def tmp(request: HttpRequest | None) -> HttpResponse:
    return render(request, "tmp.html", {})


@require_POST
def generate(request: HttpRequest) -> HttpResponse:
    """
    HTMX-эндпоинт для генерации гипнотического полутонового SVG на лету.
    Не сохраняет данные в БД (Zero-Disk / Zero-PII).
    """
    form = HalftoneGenerateForm(request.POST, request.FILES)

    if not form.is_valid():
        error_msg = next(iter(form.errors.values()))[0] if form.errors else "Ошибка параметров генерации"
        return render(request, "block/preview.html", {"error": error_msg})

    image_file = form.cleaned_data["image"]
    shape = form.cleaned_data["shape"]
    cols = form.cleaned_data["cols"]
    max_radius = form.cleaned_data["max_radius"]
    blink = form.cleaned_data["blink"]
    rotation = form.cleaned_data["rotation"]
    scale = form.cleaned_data["scale"]
    angle = form.cleaned_data["angle"]

    # Извлечение основного цвета (поддержка монотонной схемы)
    colors = request.POST.getlist("colors")
    primary_color = colors[0] if colors and colors[0] else "#a855ff"

    try:
        svg_content = generate_halftone_svg(
            image=image_file,
            cols=cols,
            max_radius=max_radius,
            shape=shape,
            color=primary_color,
            blink=blink,
            rotation=rotation,
            scale=scale,
            angle=angle,
        )
    except Exception as e:
        return render(
            request,
            "block/preview.html",
            {"error": f"Сбой в матрице гипноза: {str(e)}"},
        )

    return render(
        request,
        "block/preview.html",
        {
            "svg_content": svg_content,
            "form_data": form.cleaned_data,
            "primary_color": primary_color,
        },
    )


@require_POST
def publish(request: HttpRequest) -> HttpResponse:
    """
    HTMX-эндпоинт для сохранения текущей генерации как кандидата в галерею транса.
    Требует согласия на отслеживание (Zero-PII cookie hypn0_vid).
    """
    svg_content = request.POST.get("svg_content", "").strip()
    if not svg_content:
        return render(
            request,
            "block/publish_status.html",
            {"error": "Нет данных SVG для публикации. Попробуйте сгенерировать заново."},
        )

    visitor_uuid = request.COOKIES.get("hypn0_vid")
    if not visitor_uuid:
        # Мозговые слизняки протестуют: пользователь не дал согласия и не подчинился Гипножабе
        return render(
            request,
            "block/publish_status.html",
            {
                "not_agreed": True,
                "svg_content": svg_content,
                "shape": request.POST.get("shape", "circle"),
                "cols": request.POST.get("cols", "35"),
                "max_radius": request.POST.get("max_radius", "8"),
                "blink": request.POST.get("blink", "6"),
                "rotation": request.POST.get("rotation", "0"),
                "scale": request.POST.get("scale", "980"),
                "angle": request.POST.get("angle", "0"),
                "color": request.POST.get("color", "#a855ff"),
            },
        )

    # 1. Генерируем гипнотическое название
    title = generate_hypno_title()

    # 2. Подготавливаем SVG для галереи (пауза по умолчанию + hover)
    gallery_svg = prepare_gallery_svg(svg_content)
    svg_bytes = gallery_svg.encode("utf-8")

    # 3. Собираем параметры генерации в метаданные
    metadata = {
        "shape": request.POST.get("shape", "circle"),
        "cols": int(request.POST.get("cols", 35)) if request.POST.get("cols", "").isdigit() else 35,
        "max_radius": int(request.POST.get("max_radius", 8)) if request.POST.get("max_radius", "").isdigit() else 8,
        "blink": int(request.POST.get("blink", 6)) if request.POST.get("blink", "").isdigit() else 6,
        "rotation": int(request.POST.get("rotation", 0)) if request.POST.get("rotation", "").lstrip("-").isdigit() else 0,
        "scale": int(request.POST.get("scale", 980)) if request.POST.get("scale", "").isdigit() else 980,
        "angle": int(request.POST.get("angle", 0)) if request.POST.get("angle", "").lstrip("-").isdigit() else 0,
        "color": request.POST.get("color", "#a855ff"),
    }

    try:
        svg_file = ContentFile(svg_bytes, name="hypn0.svg")
        item = TbHypn0Item(
            s_title=title,
            file_svg=svg_file,
            i_file_size=len(svg_bytes),
            j_metadata=metadata,
            i_level=TbHypn0Item.Level.CANDIDATE,
            is_public=True,
        )
        item.save(visitor_uuid_or_fp=visitor_uuid)
    except PermissionError:
        return render(
            request,
            "block/publish_status.html",
            {
                "not_agreed": True,
                "svg_content": svg_content,
                "shape": request.POST.get("shape", "circle"),
                "cols": request.POST.get("cols", "35"),
                "max_radius": request.POST.get("max_radius", "8"),
                "blink": request.POST.get("blink", "6"),
                "rotation": request.POST.get("rotation", "0"),
                "scale": request.POST.get("scale", "980"),
                "angle": request.POST.get("angle", "0"),
                "color": request.POST.get("color", "#a855ff"),
            },
        )
    except Exception as e:
        return render(
            request,
            "block/publish_status.html",
            {"error": f"Сбой фиксации в трансе: {str(e)}"},
        )

    return render(
        request,
        "block/publish_status.html",
        {
            "success": True,
            "item": item,
        },
    )


def gallery_random(request: HttpRequest) -> HttpResponse:
    """
    Быстрый эндпоинт для случайной навигации по галерее ("в транс") и предзагрузки пула хэшей.
    Принимает список уже просмотренных хэшей в параметре `exclude` (через запятую) и текущий хэш `current`.

    Архитектура выборки:
    - Запрашивает только плоский список индексированных строк `s_hash_id` (Index Only Scan).
    - Перемешивание и срез происходят в памяти Python за доли миллисекунды без тяжелого `ORDER BY RANDOM()`.
    - Если все исключенные работы покрыли базу, фильтр сбрасывается для замыкания кольца.

    ========================================================================================
    МАСШТАБИРОВАНИЕ НА 1 000 000+ ЗАПИСЕЙ (FUTURE SCALING NOTE):
    При достижении миллионов строк в базе операция exclude(s_hash_id__in=...) может нагружать СУБД.
    Для ультра-высоких нагрузок переключить на алгоритм:
      1. count = TbHypn0Item.objects.filter(is_public=True).count()
      2. random_offset = random.randint(0, max(0, count - slice_size))
      3. pool_slice = list(TbHypn0Item.objects.filter(is_public=True)
                           .values_list('s_hash_id', flat=True)[random_offset : random_offset + slice_size])
      4. candidates = [h for h in pool_slice if h not in exclude_set and h != current]
      5. return random.sample(candidates, min(len(candidates), limit))
    ========================================================================================
    """
    exclude_raw = request.GET.get("exclude", "")
    exclude_hashes = set(h.strip() for h in exclude_raw.split(",") if h.strip())
    current_hash = request.GET.get("current", "").strip()
    if current_hash:
        exclude_hashes.add(current_hash)

    try:
        limit = min(max(int(request.GET.get("limit", 20)), 1), 50)
    except (ValueError, TypeError):
        limit = 20

    base_qs = TbHypn0Item.objects.filter(is_public=True)

    # 1. Попытка выбрать кандидатов среди еще не просмотренных
    candidate_hashes = list(
        base_qs.exclude(s_hash_id__in=exclude_hashes).values_list("s_hash_id", flat=True)[:300]
    )

    # 2. Если все просмотрены (или база меньше истории) — замыкаем кольцо, исключая только текущий
    if not candidate_hashes and current_hash:
        candidate_hashes = list(
            base_qs.exclude(s_hash_id=current_hash).values_list("s_hash_id", flat=True)[:300]
        )

    # 3. Крайний случай — берем любые доступные
    if not candidate_hashes:
        candidate_hashes = list(base_qs.values_list("s_hash_id", flat=True)[:300])

    if candidate_hashes:
        random.shuffle(candidate_hashes)
        pool = candidate_hashes[:limit]
        next_hash = pool[0]
    else:
        pool = []
        next_hash = None

    # Определение формата ответа
    is_json = (
        request.GET.get("format") == "json"
        or request.headers.get("Accept") == "application/json"
        or request.headers.get("X-Requested-With") == "XMLHttpRequest"
    )

    if is_json:
        return JsonResponse({"next_hash_id": next_hash, "pool": pool})

    if next_hash:
        return redirect("hypn0_site:gallery_detail", hash_id=next_hash)

    return redirect("hypn0_site:index")


def build_unconscious_matrix(current_hash: str, seed_param: str | None) -> tuple[list[dict], str, str, str, str, str]:
    """
    Формирует "Матрицу бессознательного" (до 200 псевдослучайных узлов) вокруг корневой картины.

    Формат seed: "<NUM>_<ORIGIN_HASH>", например "74291_a1b2c3".
    Алгоритм:
    - При первом заходе без seed генерируется seed_num и origin_hash = current_hash.
    - Выбираются -99 элементов слева и +100 элементов справа от origin_hash (всего до 200).
    - Для N <= 200 перемешиваются все доступные картины, а origin_hash помещается в центр.
    - Для текущего элемента current_hash определяются prev_hash и next_hash по кольцу.
    """
    seed_num = None
    origin_hash = current_hash

    if seed_param:
        parts = str(seed_param).split("_", 1)
        try:
            seed_num = int(parts[0])
            if len(parts) > 1 and parts[1].strip():
                origin_hash = parts[1].strip()
        except (ValueError, TypeError):
            seed_num = None

    if seed_num is None:
        seed_num = random.randint(10000, 99999)
        origin_hash = current_hash

    effective_seed = f"{seed_num}_{origin_hash}"
    rng = random.Random(seed_num)

    # 1. Запрашиваем все публичные хэши
    all_hashes = list(TbHypn0Item.objects.filter(is_public=True).values_list("s_hash_id", flat=True))

    if not all_hashes:
        all_hashes = [current_hash]

    if origin_hash not in all_hashes:
        origin_hash = current_hash

    other_hashes = [h for h in all_hashes if h != origin_hash]

    if len(other_hashes) <= 199:
        rng.shuffle(other_hashes)
        mid_idx = len(other_hashes) // 2
        trail = other_hashes[:mid_idx] + [origin_hash] + other_hashes[mid_idx:]
    else:
        chosen_others = rng.sample(other_hashes, 199)
        left_part = chosen_others[:99]
        right_part = chosen_others[99:]
        trail = left_part + [origin_hash] + right_part

    # Гарантия наличия current_hash в trail
    if current_hash not in trail:
        trail.append(current_hash)

    idx = trail.index(current_hash)
    total = len(trail)
    prev_hash = trail[(idx - 1) % total]
    next_hash = trail[(idx + 1) % total]

    prev_url = f"/gallery/{prev_hash}?seed={effective_seed}"
    next_url = f"/gallery/{next_hash}?seed={effective_seed}"

    matrix_items = [
        {
            "s_hash_id": h,
            "is_current": (h == current_hash),
            "url": f"/gallery/{h}?seed={effective_seed}",
        }
        for h in trail
    ]

    return matrix_items, prev_hash, next_hash, prev_url, next_url, effective_seed


def gallery_detail(request: HttpRequest, hash_id: str) -> HttpResponse:
    """
    Страница детального просмотра и шеринга картины из галереи транса.
    Выводит активный живой SVG, кнопки скачивания/копирования, наукообразную телеметрию
    и интерактивную Матрицу бессознательного (персональный поток хэшей по seed).
    """
    item = get_object_or_404(TbHypn0Item, s_hash_id=hash_id, is_public=True)

    # Инкремент просмотров
    item.increment_views()

    # Считывание содержимого SVG
    svg_content = ""
    if item.file_svg:
        try:
            with item.file_svg.open("r") as f:
                svg_content = f.read()
                if isinstance(svg_content, bytes):
                    svg_content = svg_content.decode("utf-8")
        except Exception:
            svg_content = ""

    active_svg = prepare_active_svg(svg_content)
    svg_stats = analyze_svg_structure(svg_content)

    # Авторский отпечаток
    author_vote = item.votes.filter(i_direction=TbVote.Direction.AUTHOR).first()
    author_fp = author_vote.s_fingerprint if author_vote else None

    # Проверка, голосовал ли текущий посетитель
    user_voted = False
    visitor_uuid = request.COOKIES.get("hypn0_vid")
    if visitor_uuid and item.pk:
        fp = hashlib.sha256(f"{visitor_uuid}:{settings.SECRET_KEY}".encode()).hexdigest()
        user_voted = item.votes.filter(s_fingerprint=fp).exists()

    # Построение матрицы бессознательного
    seed_param = request.GET.get("seed")
    matrix_items, prev_hash, next_hash, prev_url, next_url, seed = build_unconscious_matrix(
        current_hash=item.s_hash_id, seed_param=seed_param
    )

    context = {
        "item": item,
        "active_svg": active_svg,
        "raw_svg": svg_content,
        "svg_stats": svg_stats,
        "author_fp": author_fp,
        "user_voted": user_voted,
        "metadata": item.j_metadata or {},
        "matrix_items": matrix_items,
        "prev_hash": prev_hash,
        "next_hash": next_hash,
        "prev_url": prev_url,
        "next_url": next_url,
        "seed": seed,
    }
    return render(request, "gallery/detail.html", context)


def gallery_download(request: HttpRequest, hash_id: str) -> HttpResponse:
    """
    Эндпоинт для скачивания чистого SVG-файла картины.
    """
    item = get_object_or_404(TbHypn0Item, s_hash_id=hash_id, is_public=True)

    if not item.file_svg:
        raise Http404("SVG файл отсутствует")

    try:
        with item.file_svg.open("r") as f:
            svg_content = f.read()
            if isinstance(svg_content, bytes):
                svg_content = svg_content.decode("utf-8")
    except Exception:
        raise Http404("SVG файл не может быть прочитан")

    clean_svg = prepare_active_svg(svg_content)
    response = HttpResponse(clean_svg, content_type="image/svg+xml")
    filename = f"hypn0-{item.s_hash_id}.svg"
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    return response


@require_POST
def gallery_vote(request: HttpRequest, hash_id: str) -> HttpResponse:
    """
    HTMX-эндпоинт для голосования (лайк) за картину в галерее.
    """
    item = get_object_or_404(TbHypn0Item, s_hash_id=hash_id, is_public=True)
    visitor_uuid = request.COOKIES.get("hypn0_vid")

    if not visitor_uuid:
        return render(
            request,
            "block/vote_button.html",
            {
                "item": item,
                "user_voted": False,
                "not_agreed": True,
            },
        )

    voted = item.increment_likes(visitor_uuid)
    item.refresh_from_db(fields=["i_likes_count"])

    return render(
        request,
        "block/vote_button.html",
        {
            "item": item,
            "user_voted": True,
            "voted_now": voted,
        },
    )
