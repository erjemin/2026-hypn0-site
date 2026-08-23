from django.http import HttpRequest, HttpResponse
from django.shortcuts import render
from django.views.decorators.csrf import ensure_csrf_cookie
from django.views.decorators.http import require_POST

from .forms import HalftoneGenerateForm
from .services.halftone import generate_halftone_svg


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
        },
    )
