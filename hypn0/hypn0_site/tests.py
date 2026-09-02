import io
import shutil
import tempfile
from django.core.files.base import ContentFile
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, TestCase, override_settings
from django.urls import reverse
from PIL import Image

from .forms import HalftoneGenerateForm
from .models import TbHypn0Item, TbVote
from .services.halftone import (
    analyze_svg_structure,
    encode_to_base36,
    generate_halftone_svg,
    prepare_active_svg,
    prepare_gallery_svg,
)
from .services.naming import generate_hypno_title, generate_title_openrouter


class BaseMediaTestCase(TestCase):
    """Базовый тестовый класс с изоляцией MEDIA_ROOT и STORAGES во временной папке."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.temp_media = tempfile.mkdtemp()
        cls.override_media = override_settings(
            MEDIA_ROOT=cls.temp_media,
            STORAGES={
                "default": {
                    "BACKEND": "django.core.files.storage.FileSystemStorage",
                    "OPTIONS": {
                        "location": cls.temp_media,
                    },
                },
                "staticfiles": {
                    "BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage",
                },
            },
        )
        cls.override_media.enable()

    @classmethod
    def tearDownClass(cls):
        cls.override_media.disable()
        shutil.rmtree(cls.temp_media, ignore_errors=True)
        super().tearDownClass()


class HalftoneServiceTests(BaseMediaTestCase):
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


class HalftoneFormTests(BaseMediaTestCase):
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


class HalftoneViewTests(BaseMediaTestCase):
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
        self.assertContains(response, "handleFileChange")
        self.assertContains(response, "imagePreviewUrl")
        self.assertContains(response, "Гипножаба облизывается на:")
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


class NamingServiceTests(BaseMediaTestCase):
    """Тестирование сервиса гипнотических названий (services/naming.py)."""

    def test_generate_hypno_title(self):
        title = generate_hypno_title(seed=42)
        self.assertIsInstance(title, str)
        self.assertTrue(len(title) > 5)

        # Проверка детерминированности по seed
        self.assertEqual(generate_hypno_title(seed=42), title)

    def test_openrouter_stub(self):
        res = generate_title_openrouter(b"dummy_bytes")
        self.assertIsNone(res)


class GalleryPreparationTests(BaseMediaTestCase):
    """Тестирование подготовки SVG к галерейному хранению."""

    def test_prepare_gallery_svg(self):
        raw_svg = '<svg><style>.shape{animation:noise 1s}</style><g></g></svg>'
        prepared = prepare_gallery_svg(raw_svg)
        self.assertIn("svg{--hypn0-play:paused}", prepared)
        self.assertIn(":host(:hover) svg,svg:hover{--hypn0-play:running!important}", prepared)
        self.assertIn("animation-play-state:var(--hypn0-play,paused)!important", prepared)


class PublishViewTests(BaseMediaTestCase):
    """Тестирование эндпоинта публикации кандидата в галерею (/publish)."""

    def setUp(self):
        self.client = Client()
        self.sample_svg = '<svg xmlns="http://www.w3.org/2000/svg"><style>.shape{color:red}</style><g><circle/></g></svg>'

    def test_publish_without_cookie_returns_slug_protest(self):
        response = self.client.post(
            reverse("hypn0_site:publish"),
            data={
                "svg_content": self.sample_svg,
                "shape": "circle",
                "cols": "35",
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Мозговые слизняки протестуют!")
        self.assertContains(response, "Подчиниться и опубликовать")
        self.assertEqual(TbHypn0Item.objects.count(), 0)

    def test_publish_with_cookie_success(self):
        vid = "123e4567-e89b-12d3-a456-426614174000"
        self.client.cookies["hypn0_vid"] = vid

        response = self.client.post(
            reverse("hypn0_site:publish"),
            data={
                "svg_content": self.sample_svg,
                "shape": "diamond",
                "cols": "40",
                "max_radius": "6",
                "blink": "7",
                "rotation": "5",
                "scale": "950",
                "angle": "10",
                "color": "#10b981",
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Уже в галерее транса")
        self.assertContains(response, "идет прорастание психо-паутины...")

        # Проверяем запись в БД
        self.assertEqual(TbHypn0Item.objects.count(), 1)
        item = TbHypn0Item.objects.first()
        self.assertTrue(len(item.s_hash_id) >= 6)
        self.assertIn(f"#{item.s_hash_id}", response.content.decode("utf-8"))
        self.assertEqual(item.i_level, TbHypn0Item.Level.CANDIDATE)
        self.assertEqual(item.i_likes_count, 1)
        self.assertEqual(item.j_metadata["shape"], "diamond")
        self.assertEqual(item.j_metadata["cols"], 40)
        self.assertEqual(item.j_metadata["color"], "#10b981")

        # Проверяем авторский голос в TbVote
        self.assertEqual(TbVote.objects.count(), 1)
        author_vote = TbVote.objects.first()
        self.assertEqual(author_vote.k_item, item)
        self.assertEqual(author_vote.i_direction, TbVote.Direction.AUTHOR)

    def test_publish_empty_svg_returns_error(self):
        self.client.cookies["hypn0_vid"] = "123e4567-e89b-12d3-a456-426614174000"
        response = self.client.post(
            reverse("hypn0_site:publish"),
            data={"svg_content": ""},
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Нет данных SVG для публикации")
        self.assertEqual(TbHypn0Item.objects.count(), 0)


class SvgAnalysisAndActiveSvgTests(BaseMediaTestCase):
    """Тестирование анализа структуры SVG и очистки от паузы."""

    def test_prepare_active_svg(self):
        gallery_svg = '<svg><style>svg:not(:hover) .shape,svg:not(:hover) circle,svg:not(:hover) rect,svg:not(:hover) polygon,svg:not(:hover) path{animation-play-state:paused!important}</style><g></g></svg>'
        active = prepare_active_svg(gallery_svg)
        self.assertNotIn("animation-play-state:paused!important", active)

    def test_prepare_active_svg_preserves_color_and_animation(self):
        gallery_svg = (
            '<svg xmlns="http://www.w3.org/2000/svg">'
            '<style>'
            'svg{background:transparent}'
            '.shape,circle,rect,polygon,path{fill:#e6b400;stroke:#e6b400;opacity:0.90;transform-origin:center;animation:noise 1.36s ease-in-out infinite alternate;animation-delay:var(--d);animation-play-state:var(--hypn0-play,running);transition:all .5s ease-out}'
            '@keyframes noise{0%{opacity:0.63}100%{opacity:0.45}}'
            'svg{--hypn0-play:paused}svg:hover{--hypn0-play:running}.shape,circle,rect,polygon,path{animation-play-state:var(--hypn0-play,paused)!important}'
            '</style><g></g></svg>'
        )
        active = prepare_active_svg(gallery_svg)
        self.assertIn("fill:#e6b400", active)
        self.assertIn("stroke:#e6b400", active)
        self.assertIn("animation:noise 1.36s", active)
        self.assertNotIn("svg{--hypn0-play:paused}", active)
        self.assertNotIn("animation-play-state:var(--hypn0-play,paused)!important", active)

    def test_analyze_svg_structure(self):
        svg = (
            '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 800 600">'
            '<style>.a0{--d:0s}.a1{--d:1s}@keyframes noise{0%{opacity:1}100%{opacity:0.5}}</style>'
            '<defs><circle id="s0" r="5"/><rect id="s1" width="10" height="10"/></defs>'
            '<g id="hypn0-canvas">'
            '<g class="a0"><use href="#s0" x="10" y="10"/><use href="#s0" x="20" y="20"/></g>'
            '<g class="a1"><use href="#s1" x="30" y="30"/></g>'
            '</g>'
            '</svg>'
        )
        stats = analyze_svg_structure(svg)
        self.assertEqual(stats["use_count"], 3)
        self.assertEqual(stats["total_oscillators"], 3)
        self.assertEqual(stats["defs_count"], 2)
        self.assertEqual(stats["circle_count"], 1)
        self.assertEqual(stats["rect_count"], 1)
        self.assertEqual(stats["groups_count"], 3)
        self.assertEqual(stats["keyframes_count"], 1)
        self.assertEqual(stats["viewbox"], "0 0 800 600")
        self.assertEqual(stats["width"], 800)
        self.assertEqual(stats["height"], 600)
        self.assertEqual(stats["aspect_ratio"], "4:3")
        self.assertTrue(stats["total_bytes"] > 0)


class GalleryDetailAndDownloadTests(BaseMediaTestCase):
    """Тестирование страниц детального просмотра картины, скачивания и голосования."""

    def setUp(self):
        self.client = Client()
        self.vid = "123e4567-e89b-12d3-a456-426614174000"
        svg_code = (
            '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1000 1000">'
            '<style>.a0{--d:0s}svg:not(:hover) .shape,svg:not(:hover) circle,svg:not(:hover) rect,svg:not(:hover) polygon,svg:not(:hover) path{animation-play-state:paused!important}</style>'
            '<defs><circle id="s0" r="8"/></defs>'
            '<g id="hypn0-canvas"><g class="a0"><use href="#s0" x="50" y="50"/></g></g>'
            '</svg>'
        )
        self.item = TbHypn0Item(
            s_title="Астральный Транс Сознания #42",
            file_svg=ContentFile(svg_code.encode("utf-8"), name="test_item.svg"),
            i_file_size=len(svg_code),
            j_metadata={
                "shape": "circle",
                "cols": 35,
                "max_radius": 8,
                "blink": 6,
                "rotation": 0,
                "scale": 980,
                "angle": 0,
                "color": "#a855ff",
            },
            i_level=TbHypn0Item.Level.CANDIDATE,
            is_public=True,
        )
        self.item.save(visitor_uuid_or_fp=self.vid)

    def test_gallery_detail_view_success(self):
        response = self.client.get(reverse("hypn0_site:gallery_detail", kwargs={"hash_id": self.item.s_hash_id}))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Астральный Транс Сознания #42")
        self.assertContains(response, f"#{self.item.s_hash_id}")
        self.assertContains(response, "Векторная анатомия")
        self.assertContains(response, "Синтез психо-сетки")
        self.assertContains(response, "Астральный паспорт")
        self.assertContains(response, "Копировать SVG-код")
        self.assertContains(response, "Скачать .svg")

        # Проверка инкремента просмотров
        self.item.refresh_from_db()
        self.assertGreaterEqual(self.item.i_views_count, 2)

    def test_gallery_detail_404_on_invalid_hash(self):
        response = self.client.get(reverse("hypn0_site:gallery_detail", kwargs={"hash_id": "nonexistent999"}))
        self.assertEqual(response.status_code, 404)

    def test_gallery_download_view_success(self):
        response = self.client.get(reverse("hypn0_site:gallery_download", kwargs={"hash_id": self.item.s_hash_id}))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "image/svg+xml")
        self.assertIn(f'filename="hypn0-{self.item.s_hash_id}.svg"', response["Content-Disposition"])
        # Должен быть чистый активный SVG (без паузы анимации)
        self.assertNotIn("animation-play-state:paused!important", response.content.decode("utf-8"))

    def test_gallery_vote_with_cookie(self):
        # Новый посетитель
        voter_vid = "987e6543-e21b-12d3-a456-426614174999"
        self.client.cookies["hypn0_vid"] = voter_vid
        response = self.client.post(reverse("hypn0_site:gallery_vote", kwargs={"hash_id": self.item.s_hash_id}))
        self.assertEqual(response.status_code, 200)
        self.item.refresh_from_db()
        self.assertEqual(self.item.i_likes_count, 2)

    def test_gallery_vote_without_cookie_returns_notice(self):
        client = Client()
        response = client.post(reverse("hypn0_site:gallery_vote", kwargs={"hash_id": self.item.s_hash_id}))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Подчинитесь воле Гипножабы!")


class GalleryRandomAndNavigationTests(BaseMediaTestCase):
    """Тестирование случайной навигации и пула хэшей (/gallery/random)."""

    def setUp(self):
        self.client = Client()
        self.vid = "123e4567-e89b-12d3-a456-426614174000"

        # Создаем 3 картины в галерее
        self.items = []
        for i in range(3):
            svg_code = f'<svg><g id="item_{i}"></g></svg>'
            item = TbHypn0Item(
                s_title=f"Гипно Картина #{i}",
                file_svg=ContentFile(svg_code.encode("utf-8"), name=f"test_item_{i}.svg"),
                i_file_size=len(svg_code),
                j_metadata={"cols": 30 + i},
                is_public=True,
            )
            item.save(visitor_uuid_or_fp=self.vid)
            self.items.append(item)

    def test_gallery_random_direct_redirect(self):
        response = self.client.get(reverse("hypn0_site:gallery_random"))
        self.assertEqual(response.status_code, 302)
        all_hashes = [it.s_hash_id for it in self.items]
        self.assertTrue(any(h in response.url for h in all_hashes))

    def test_gallery_random_json_pool(self):
        response = self.client.get(reverse("hypn0_site:gallery_random"), data={"format": "json", "limit": 2})
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("next_hash_id", data)
        self.assertIn("pool", data)
        self.assertEqual(len(data["pool"]), 2)
        all_hashes = {it.s_hash_id for it in self.items}
        self.assertIn(data["next_hash_id"], all_hashes)

    def test_gallery_random_exclude_filters_seen(self):
        exclude_hashes = [self.items[0].s_hash_id, self.items[1].s_hash_id]
        response = self.client.get(
            reverse("hypn0_site:gallery_random"),
            data={"format": "json", "exclude": ",".join(exclude_hashes)},
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["next_hash_id"], self.items[2].s_hash_id)

    def test_gallery_random_exclude_all_loops_circle(self):
        # Если исключены все 3 картины, кольцо замыкается
        exclude_hashes = [it.s_hash_id for it in self.items]
        response = self.client.get(
            reverse("hypn0_site:gallery_random"),
            data={
                "format": "json",
                "exclude": ",".join(exclude_hashes),
                "current": self.items[0].s_hash_id,
            },
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIsNotNone(data["next_hash_id"])
        # Текущий элемент исключен, выбран один из оставшихся
        self.assertIn(data["next_hash_id"], [self.items[1].s_hash_id, self.items[2].s_hash_id])

    def test_gallery_random_empty_database(self):
        TbHypn0Item.objects.all().delete()
        # Direct visit redirects to index
        response = self.client.get(reverse("hypn0_site:gallery_random"))
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse("hypn0_site:index"))

        # JSON returns null next_hash_id
        json_resp = self.client.get(reverse("hypn0_site:gallery_random"), data={"format": "json"})
        self.assertEqual(json_resp.status_code, 200)
        self.assertIsNone(json_resp.json()["next_hash_id"])
        self.assertEqual(json_resp.json()["pool"], [])


class UnconsciousMatrixTests(BaseMediaTestCase):
    """Тестирование Матрицы бессознательного (build_unconscious_matrix) и навигации."""

    def setUp(self):
        self.client = Client()
        self.vid = "123e4567-e89b-12d3-a456-426614174000"

        # Создаем 5 картин
        self.items = []
        for i in range(5):
            svg_code = f'<svg><circle id="dot_{i}"/></svg>'
            item = TbHypn0Item(
                s_title=f"Тестовый транс #{i}",
                file_svg=ContentFile(svg_code.encode("utf-8"), name=f"test_matrix_{i}.svg"),
                i_file_size=len(svg_code),
                j_metadata={"cols": 20 + i},
                is_public=True,
            )
            item.save(visitor_uuid_or_fp=self.vid)
            self.items.append(item)

    def test_build_unconscious_matrix_basic(self):
        from hypn0_site.views import build_unconscious_matrix

        current = self.items[0].s_hash_id
        matrix_items, prev_h, next_h, prev_url, next_url, seed = build_unconscious_matrix(current, None)

        self.assertEqual(len(matrix_items), 5)
        # Проверяем, что current отмечен как is_current
        current_node = [n for n in matrix_items if n["s_hash_id"] == current][0]
        self.assertTrue(current_node["is_current"])

        # Другие узлы не current
        other_nodes = [n for n in matrix_items if n["s_hash_id"] != current]
        self.assertTrue(all(not n["is_current"] for n in other_nodes))

        # Ссылки содержат seed
        self.assertIn(f"seed={seed}", prev_url)
        self.assertIn(f"seed={seed}", next_url)

    def test_matrix_stability_with_fixed_seed(self):
        from hypn0_site.views import build_unconscious_matrix

        root_hash = self.items[2].s_hash_id
        fixed_seed = f"42109_{root_hash}"

        # Первый запрос
        m1, prev1, next1, _, _, seed1 = build_unconscious_matrix(self.items[0].s_hash_id, fixed_seed)
        # Второй запрос с тем же seed на другую картину
        m2, prev2, next2, _, _, seed2 = build_unconscious_matrix(self.items[1].s_hash_id, fixed_seed)

        self.assertEqual(seed1, fixed_seed)
        self.assertEqual(seed2, fixed_seed)

        # Состав и порядок хэшей в матрице должны быть идентичны
        hashes1 = [n["s_hash_id"] for n in m1]
        hashes2 = [n["s_hash_id"] for n in m2]
        self.assertEqual(hashes1, hashes2)

    def test_gallery_detail_renders_matrix_and_card_bg_style(self):
        item = self.items[0]
        response = self.client.get(reverse("hypn0_site:gallery_detail", kwargs={"hash_id": item.s_hash_id}))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Матрица бессознательного")
        self.assertContains(response, "5 узлов")
        self.assertContains(response, f"#{item.s_hash_id}")
        self.assertContains(response, "btn-nav-prev")
        self.assertContains(response, "btn-nav-next")
        self.assertContains(response, "--card-bg-light")
        self.assertContains(response, "--card-bg-dark")
        self.assertContains(response, "bg-[var(--card-bg-light)]")


class GalleryFreshFloorTests(BaseMediaTestCase):
    """Тестирование 1-го этажа («Плеск бессознательного»), выборки и пагинации."""

    def setUp(self):
        self.client = Client()
        self.vid = "123e4567-e89b-12d3-a456-426614174000"

    def test_get_floor_fresh_filtering_and_ordering(self):
        from hypn0_site.views import get_floor_fresh

        # 1. Создаем картины разных уровней и с разным числом просмотров
        svg_bytes = b'<svg><circle/></svg>'

        # Свежий кандидат с 5 просмотрами
        item_cand = TbHypn0Item(
            s_title="Кандидат",
            file_svg=ContentFile(svg_bytes, name="c.svg"),
            i_views_count=5,
            i_level=TbHypn0Item.Level.CANDIDATE,
            is_public=True,
        )
        item_cand.save(visitor_uuid_or_fp=self.vid)

        # Level 1 с 1 просмотром (должен быть первым, т.к. просмотров меньше)
        item_lvl1 = TbHypn0Item(
            s_title="Level 1",
            file_svg=ContentFile(svg_bytes, name="l1.svg"),
            i_views_count=1,
            i_level=TbHypn0Item.Level.LEVEL_1,
            is_public=True,
        )
        item_lvl1.save(visitor_uuid_or_fp=self.vid)

        # Level 2 (2-й этаж, не должен попасть в 1-й)
        item_lvl2 = TbHypn0Item(
            s_title="Level 2 Curated",
            file_svg=ContentFile(svg_bytes, name="l2.svg"),
            i_views_count=0,
            i_level=TbHypn0Item.Level.LEVEL_2,
            is_public=True,
        )
        item_lvl2.save(visitor_uuid_or_fp=self.vid)

        # Непубличная картина (не должна попасть)
        item_private = TbHypn0Item(
            s_title="Private",
            file_svg=ContentFile(svg_bytes, name="p.svg"),
            i_views_count=0,
            i_level=TbHypn0Item.Level.CANDIDATE,
            is_public=False,
        )
        item_private.save(visitor_uuid_or_fp=self.vid)

        results = list(get_floor_fresh(limit=10))
        self.assertEqual(len(results), 2)
        # Сначала с наименьшим i_views_count
        self.assertEqual(results[0].pk, item_lvl1.pk)
        self.assertEqual(results[1].pk, item_cand.pk)

    def test_index_view_renders_fresh_stream(self):
        # Создаем 2 картины для 1 этажа
        svg_bytes = b'<svg><circle/></svg>'
        item = TbHypn0Item(
            s_title="Свежий шедевр",
            file_svg=ContentFile(svg_bytes, name="f1.svg"),
            i_views_count=2,
            i_level=TbHypn0Item.Level.CANDIDATE,
            is_public=True,
        )
        item.save(visitor_uuid_or_fp=self.vid)

        response = self.client.get(reverse("hypn0_site:index"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Плеск бессознательного")
        self.assertContains(response, "FRESH STREAM")
        self.assertContains(response, f"gallery-card-{item.s_hash_id}")
        self.assertContains(response, f"¤{item.s_hash_id}")

    def test_publish_includes_oob_swap_for_fresh_grid(self):
        self.client.cookies["hypn0_vid"] = self.vid
        sample_svg = '<svg xmlns="http://www.w3.org/2000/svg"><g><circle/></g></svg>'

        response = self.client.post(
            reverse("hypn0_site:publish"),
            data={
                "svg_content": sample_svg,
                "shape": "circle",
                "cols": "35",
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'hx-swap-oob="afterbegin:#fresh-stream-grid"')
        item = TbHypn0Item.objects.first()
        self.assertContains(response, f"gallery-card-{item.s_hash_id}")

    def test_gallery_floor_fresh_pagination(self):
        # Создаем 10 картин
        svg_bytes = b'<svg><circle/></svg>'
        for i in range(10):
            item = TbHypn0Item(
                s_title=f"Кандидат #{i}",
                file_svg=ContentFile(svg_bytes, name=f"cand_{i}.svg"),
                i_views_count=i,
                i_level=TbHypn0Item.Level.CANDIDATE,
                is_public=True,
            )
            item.save(visitor_uuid_or_fp=self.vid)

        # Страница 1 (должно быть 8 штук)
        url = reverse("hypn0_site:gallery_floor", kwargs={"floor_slug": "fresh"})
        response_p1 = self.client.get(url)
        self.assertEqual(response_p1.status_code, 200)
        self.assertContains(response_p1, "Плеск бессознательного")
        self.assertContains(response_p1, "FRESH STREAM")
        self.assertEqual(len(response_p1.context["page_obj"]), 8)
        self.assertContains(response_p1, "Фаза 1 из 2")

        # Страница 2 (должно быть 2 штуки)
        response_p2 = self.client.get(url, data={"page": 2})
        self.assertEqual(response_p2.status_code, 200)
        self.assertEqual(len(response_p2.context["page_obj"]), 2)
        self.assertContains(response_p2, "Фаза 2 из 2")

    def test_gallery_floor_unknown_404(self):
        url = reverse("hypn0_site:gallery_floor", kwargs={"floor_slug": "non_existent"})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 404)


class CardBgStyleTests(BaseMediaTestCase):
    """Тестирование вычисления адаптивных стилей подложки карточки."""

    def test_extreme_white_color_forces_dark_background(self):
        item = TbHypn0Item(j_metadata={"color": "#ffffff"})
        style = item.card_bg_style
        self.assertIn("--card-bg-light: rgb(12, 12, 15);", style)
        self.assertIn("--card-bg-dark: rgb(12, 12, 15);", style)

    def test_extreme_black_color_forces_light_background(self):
        item = TbHypn0Item(j_metadata={"color": "#000000"})
        style = item.card_bg_style
        self.assertIn("--card-bg-light: rgb(244, 244, 246);", style)
        self.assertIn("--card-bg-dark: rgb(244, 244, 246);", style)

    def test_colorful_intermediate_color_creates_theme_adaptive_background(self):
        item = TbHypn0Item(j_metadata={"color": "#a855ff"})
        style = item.card_bg_style
        self.assertIn("--card-bg-light: rgb(250, 247, 252);", style)
        self.assertIn("--card-bg-dark: rgb(20, 14, 33);", style)

    def test_fallback_on_empty_or_invalid_color(self):
        item_none = TbHypn0Item(j_metadata=None)
        self.assertIn("--card-bg-light:", item_none.card_bg_style)
        self.assertIn("--card-bg-dark:", item_none.card_bg_style)

        item_invalid = TbHypn0Item(j_metadata={"color": "invalid-hex"})
        self.assertIn("--card-bg-light:", item_invalid.card_bg_style)
        self.assertIn("--card-bg-dark:", item_invalid.card_bg_style)

    def test_card_svg_property_and_shadow_dom_rendering(self):
        item = TbHypn0Item(
            s_title="Тестовый SVG",
            file_svg=ContentFile(b'<svg id="test-svg"><circle/></svg>', name="test_card.svg"),
            j_metadata={"color": "#10b981"},
            is_public=True,
        )
        item.save(visitor_uuid_or_fp="123e4567-e89b-12d3-a456-426614174000")
        self.assertIn('id="test-svg"', item.card_svg)

        response = self.client.get(reverse("hypn0_site:index"))
        self.assertContains(response, 'template shadowrootmode="open"')
        self.assertContains(response, "hypn0-card-svg")
        self.assertContains(response, "--hypn0-play: running !important")
