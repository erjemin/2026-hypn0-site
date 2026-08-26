from django.core.files.base import ContentFile
from django.http import HttpRequest, HttpResponse
from django.shortcuts import render
from django.views.decorators.csrf import ensure_csrf_cookie
from django.views.decorators.http import require_POST

from .forms import HalftoneGenerateForm
from .models import TbHypn0Item
from .services.halftone import generate_halftone_svg, prepare_gallery_svg
from .services.naming import generate_hypno_title


@ensure_csrf_cookie
def index(request: HttpRequest | None) -> HttpResponse:
    return render(request, "index.html", {})


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
