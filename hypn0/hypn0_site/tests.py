import io
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, TestCase
from django.urls import reverse
from PIL import Image

from .forms import HalftoneGenerateForm
from .services.halftone import encode_to_base36, generate_halftone_svg


class HalftoneServiceTests(TestCase):
    """Тестирование сервиса генерации SVG (services/halftone.py)."""

    def setUp(self):
        # Создаем простое тестовое изображение 50x50 с градиентом
        self.img = Image.new("RGB", (50, 50), color="white")
        for x in range(25):
            for y in range(50):
                self.img.putpixel((x, y), (0, 0, 0))

    def test_encode_to_base36(self):
        self.assertEqual(encode_to_base36(0), "a")
        self.assertEqual(encode_to_base36(1), "b")
        with self.assertRaises(ValueError):
            encode_to_base36(-1)

    def test_generate_default_svg(self):
        svg = generate_halftone_svg(self.img, cols=30, max_radius=6)
        self.assertIn("<svg", svg)
        self.assertIn("</svg>", svg)
        self.assertIn("<defs>", svg)
        self.assertIn('<circle id="s', svg)
        self.assertIn('<g id="hypn0-canvas">', svg)

    def test_generate_shapes(self):
        shapes = ["circle", "ring", "square", "diamond", "triangle", "hexagon", "star", "cross", "line", "wave", "heart"]
        for shape in shapes:
            svg = generate_halftone_svg(self.img, cols=20, max_radius=5, shape=shape)
            self.assertIn("<svg", svg)
            self.assertIn("</svg>", svg)
            self.assertIn("<defs>", svg)

    def test_generate_static_blink_zero(self):
        svg = generate_halftone_svg(self.img, cols=20, blink=0)
        self.assertIn("animation:none", svg)
        self.assertNotIn("@keyframes noise", svg)

    def test_generate_animated_params(self):
        svg = generate_halftone_svg(
            self.img,
            cols=20,
            blink=8,
            rotation=12,
            scale=920,
            angle=15,
            color="#ff5500",
        )
        self.assertIn("@keyframes noise", svg)
        self.assertIn("rotate(12deg)", svg)
        self.assertIn("scale(0.92)", svg)
        self.assertIn("#ff5500", svg)

    def test_generate_from_bytes(self):
        buf = io.BytesIO()
        self.img.save(buf, format="PNG")
        svg = generate_halftone_svg(buf.getvalue(), cols=20)
        self.assertIn("<svg", svg)

    def test_generate_aspect_ratios(self):
        # Проверяем, что для вертикального изображения (100x300) сетка не раздувается
        tall_img = Image.new("RGB", (100, 300), color="black")
        svg_tall = generate_halftone_svg(tall_img, cols=30, max_radius=5)
        # При cols=30 наибольшая сторона (высота) должна иметь 30 точек, а ширина 10
        # step = 5 * 2 + 2 = 12 -> width = 10 * 12 = 120, height = 30 * 12 = 360
        self.assertIn('viewBox="0 0 120 360"', svg_tall)

        # Для горизонтального изображения (300x100)
        wide_img = Image.new("RGB", (300, 100), color="black")
        svg_wide = generate_halftone_svg(wide_img, cols=30, max_radius=5)
        self.assertIn('viewBox="0 0 360 120"', svg_wide)


class HalftoneFormTests(TestCase):
    """Тестирование формы валидации HalftoneGenerateForm."""

    def test_form_validation(self):
        buf = io.BytesIO()
        img = Image.new("RGB", (30, 30), color="red")
        img.save(buf, format="PNG")
        buf.seek(0)

        uploaded = SimpleUploadedFile("test.png", buf.read(), content_type="image/png")
        form = HalftoneGenerateForm(
            data={
                "shape": "square",
                "cols": 60,
                "max_radius": 7,
                "blink": 5,
                "rotation": 10,
                "scale": 950,
                "angle": -10,
            },
            files={"image": uploaded},
        )
        self.assertTrue(form.is_valid())
        self.assertEqual(form.cleaned_data["shape"], "square")
        self.assertEqual(form.cleaned_data["cols"], 60)


class HalftoneViewTests(TestCase):
    """Тестирование view-обработчиков (index, generate)."""

    def setUp(self):
        self.client = Client()

    def test_index_page(self):
        response = self.client.get(reverse("hypn0_site:index"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "logo-hypn0.svg")
        self.assertContains(response, 'id="preview"')
        self.assertContains(response, 'name="csrfmiddlewaretoken"')
        self.assertContains(response, 'X-CSRFToken')
        # Проверяем, что csrf_token не пустой в hx-headers
        content = response.content.decode("utf-8")
        self.assertNotIn('hx-headers=\'{"X-CSRFToken": ""}\'', content)

    def test_generate_with_enforce_csrf(self):
        csrf_client = Client(enforce_csrf_checks=True)
        response = csrf_client.get(reverse("hypn0_site:index"))
        self.assertEqual(response.status_code, 200)

        buf = io.BytesIO()
        img = Image.new("RGB", (40, 40), color="black")
        img.save(buf, format="PNG")
        buf.seek(0)

        uploaded = SimpleUploadedFile("test.png", buf.read(), content_type="image/png")
        # Без CSRF токена вернет 403
        bad_response = csrf_client.post(
            reverse("hypn0_site:generate"),
            data={"shape": "circle", "image": uploaded},
        )
        self.assertEqual(bad_response.status_code, 403)

        # С CSRF токеном в POST data вернет 200
        csrf_token = response.cookies["csrftoken"].value
        buf.seek(0)
        uploaded = SimpleUploadedFile("test.png", buf.read(), content_type="image/png")
        good_response = csrf_client.post(
            reverse("hypn0_site:generate"),
            data={
                "csrfmiddlewaretoken": csrf_token,
                "shape": "circle",
                "image": uploaded,
            },
        )
        self.assertEqual(good_response.status_code, 200)
        self.assertContains(good_response, "<svg")

        # С CSRF токеном в заголовке X-CSRFToken (как отправляет HTMX) вернет 200
        buf.seek(0)
        uploaded = SimpleUploadedFile("test.png", buf.read(), content_type="image/png")
        header_response = csrf_client.post(
            reverse("hypn0_site:generate"),
            data={
                "shape": "circle",
                "image": uploaded,
            },
            HTTP_X_CSRFTOKEN=csrf_token,
        )
        self.assertEqual(header_response.status_code, 200)
        self.assertContains(header_response, "<svg")

    def test_generate_get_not_allowed(self):
        response = self.client.get(reverse("hypn0_site:generate"))
        self.assertEqual(response.status_code, 405)

    def test_generate_post_no_image(self):
        response = self.client.post(reverse("hypn0_site:generate"), data={"shape": "circle"})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Покорми Гипножабу")

    def test_generate_post_success(self):
        buf = io.BytesIO()
        img = Image.new("RGB", (40, 40), color="black")
        img.save(buf, format="PNG")
        buf.seek(0)

        uploaded = SimpleUploadedFile("test.png", buf.read(), content_type="image/png")
        response = self.client.post(
            reverse("hypn0_site:generate"),
            data={
                "shape": "diamond",
                "cols": "40",
                "max_radius": "6",
                "blink": "6",
                "colors": ["#10b981"],
                "image": uploaded,
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "<svg")
        self.assertContains(response, 'points="0,-6')
        self.assertContains(response, "like-to-gallery")
