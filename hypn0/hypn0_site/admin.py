# Кастомная конфигурация Django Admin для Hypn0.
# Регистрируем модели с удобным интерфейсом.

import etpgrf
import random
import re
import pytils
from django import forms
from django.contrib import admin
from django.forms import Textarea
from django.utils.html import format_html
from django.utils.safestring import mark_safe
from django.http import HttpRequest
from bs4 import BeautifulSoup
from html import unescape
from .models import (
    TbHypn0Item,
    TbVote,
    TbBlogPost
)

# ============================================================================
# ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ
# ============================================================================
def clean_html_to_plain_text(html_content: str) -> str:
    """
    Очищает HTML-контент от тегов, скриптов, стилей и декодирует HTML-сущности.
    Возвращает чистый читаемый текст.
    """
    if not html_content:
        return ""
    soup = BeautifulSoup(html_content, "html.parser")
    # Скрипты, стили и форматирование вырезаем целиком
    for tag in soup(["script", "style", "noscript", "code", "kbd", "pre"]):
        tag.decompose()
    return unescape(soup.get_text()).strip()


# ============================================================================
# МИКСИНЫ ДЛЯ АДМИНКИ
# ============================================================================
class RequestInFormMixin(admin.ModelAdmin):
    """
    Миксин для передачи request объекта в форму.

    Используется когда форма нуждается в доступе к request для проверки POST параметров
    или другой информации о текущем HTTP-запросе.

    Переопределяет get_form() и передает request в __init__ формы через kwargs.
    """

    def get_form(self, request: HttpRequest, obj=None, **kwargs):
        """
        Переопределяем get_form чтобы передать request в форму.
        Создаем оборачивающий класс который передаст request в __init__.
        """
        FormClass = super().get_form(request, obj, **kwargs)

        # Сохраняем request в замыкании для доступа в классе
        request_ref = request

        class FormWithRequest(FormClass):
            """Оборачивающий класс, который передает request при инстанцировании"""
            def __init__(form_instance, *args, **init_kwargs):
                # Добавляем request в kwargs перед вызовом __init__ родителя
                init_kwargs['request'] = request_ref
                super().__init__(*args, **init_kwargs)

        return FormWithRequest


class CodeMirrorFormMixin(forms.ModelForm):
    """
    Миксин для форм с поддержкой CodeMirror редактора.

    Предоставляет:
    - Готовый Media класс с CSS и JS для CodeMirror
    - Helper метод setup_codemirror_field() для конфигурации полей
    - Базовые атрибуты для активации CodeMirror

    Использование:
        class MyForm(CodeMirrorFormMixin):
            class Meta:
                model = MyModel
                fields = (...)

            def __init__(self, *args, **kwargs):
                super().__init__(*args, **kwargs)
                self.setup_codemirror_field('field_name', 'json', 'codemirror-width-l')
    """

    # ===== MEDIA КЛАСС ДЛЯ CODEMIRROR =====
    class Media:
        """Подключаем CSS и JS для CodeMirror редактора"""
        css = {
            'all': ('codemirror/codemirror-styles.css',)  # Стили для CodeMirror
        }
        js = (
            'codemirror/editor.js',              # Основной CodeMirror
            'codemirror/codemirror-patch.js',    # Патч для управления высотой/шириной
        )

    # ===== БАЗОВЫЕ АТРИБУТЫ CODEMIRROR =====
    CODEMIRROR_ATTRS_BASE = {
        'data-codemirror-editor': '1',
        'data-width': '100%',  # Ширина для патча (100% займет полную ширину)
    }

    def setup_codemirror_field(self, field_name: str, language: str = 'text', css_class: str = 'codemirror-width-l'):
        """
        Конфигурирует поле для использования CodeMirror редактором.

        Применяет Textarea виджет с нужными атрибутами и CSS классами для CodeMirror.

        Args:
            field_name: Имя поля в форме (например, 's_label')
            language: Язык для подсветки синтаксиса (text, json, html, url и т.д.)
            css_class: CSS класс для управления размерами (codemirror-width-s, codemirror-width-l и т.д.)

        Пример:
            def __init__(self, *args, **kwargs):
                super().__init__(*args, **kwargs)
                self.setup_codemirror_field('s_label', 'text', 'codemirror-width-xl codemirror-no-lines')
                self.setup_codemirror_field('j_metadata', 'json', 'codemirror-width-l')
        """
        # Собираем атрибуты для поля
        attrs = {
            **self.CODEMIRROR_ATTRS_BASE,
            'data-language': language,
            'class': css_class,
        }

        # Применяем Textarea виджет с атрибутами
        self.fields[field_name].widget = Textarea(attrs=attrs)


# ----
# АДМИНКА ГИПНОКАРТИН
# Кастомная форма
class TbHypn0ItemAdminForm(CodeMirrorFormMixin):
    """
    Кастомная форма для админки svg-генераций (TbHypn0Item).
    Добавляет виджеты CodeMirror для текстовых полей.
    """

    class Meta:
        model = TbHypn0Item
        fields = (
            's_title', "s_promo_title", "s_promo_url", "i_level",
            "i_likes_count", "i_views_count", "i_claims_count", "f_score",
            "i_promo_clicks",

        )

    def __init__(self, *args, **kwargs):
        """
        При инициализации формы подгружаем CodeMirror редактор.
        Получаем request из kwargs, переданных из get_form_kwargs в AdminClass.
        """
        # Извлекаем request из kwargs если он есть
        self.request = kwargs.pop('request', None)

        super().__init__(*args, **kwargs)

        # Конфигурируем поля для CodeMirror
        self.setup_codemirror_field('s_title', language='text',
                                    css_class='codemirror-width-l codemirror-no-lines')
        self.setup_codemirror_field('s_promo_title', language='text',
                                    css_class='codemirror-width-l codemirror-no-lines')
        self.setup_codemirror_field('s_promo_url', language='text',
                                    css_class='codemirror-width-xl codemirror-no-lines')
        self.setup_codemirror_field('i_likes_count', language='text',
                                    css_class='codemirror-width-s codemirror-no-lines')
        self.setup_codemirror_field('i_claims_count', language='text',
                                    css_class='codemirror-width-s codemirror-no-lines')
        self.setup_codemirror_field('i_views_count', language='text',
                                    css_class='codemirror-width-s codemirror-no-lines')
        self.setup_codemirror_field('f_score', language='text',
                                    css_class='codemirror-width-s codemirror-no-lines')
        self.setup_codemirror_field('i_promo_clicks', language='text',
                                    css_class='codemirror-width-s codemirror-no-lines')
        self.setup_codemirror_field('j_metadata', language='json',
                                    css_class='codemirror-width-sl codemirror-min-height-10')

# Конфигурация админки
@admin.register(TbHypn0Item)
class TbHypn0ItemAdmin(admin.ModelAdmin):
    """
    Панель управления гипно-картинами (модерация, просмотр статистики, редактирование).
    Создание новых картин через админку заблокировано (создание только на фронтенде).
    """
    form = TbHypn0ItemAdminForm
    list_display = ("id", "s_hash_id",  "title_preview", "i_level", "i_likes_count", "i_claims_count",
        "i_views_count", "file_size_display", "f_score", "is_public", "d_created_at", )
    list_display_links = ("id", "s_hash_id", "title_preview")
    list_filter = ("i_level", "is_public", "d_created_at")
    search_fields = ("s_hash_id", "s_title", "s_promo_title", "s_promo_url")
    readonly_fields = ("id", "s_hash_id", "file_size_display", "d_created_at", "d_updated_at", "svg_preview",)
    fieldsets = (
        ("ID & Hash-ID", {
            "fields": (("id", "s_hash_id",), ),
            "classes": ("collapse", ),
        }),
        ("Основная информация", {
            "fields": ("s_title", ("file_svg", "svg_preview", "file_size_display", "is_public", ), )
        }),
        ("Модерация и Smart Retention", {
            "fields": (("i_level", "f_score", ), ),
            "description": "Уровень модерации и рейтинг 'гравитации' для ротации и очистки хранилища.",
        }),
        ("Метрики популярности", {
            "fields": ("i_likes_count", "i_claims_count", "i_views_count", ),
            "classes": ("collapse", ),
        }),
        ("Промо-блок (Спонсоры и Авторы)", {
            "fields": ("s_promo_url", "s_promo_title", "i_promo_clicks", ),
            "classes": ("collapse",),
        }),
        ("Метаданные генерации", {
            "fields": ("j_metadata",),
        }),
        ("Штампы времени", {
            "fields": ("d_created_at", "d_updated_at"),
            "classes": ("collapse",),
        }),
    )

    def has_add_permission(self, request):
        # Создание картин возможно только с фронтенда (требуется обработка растра и согласие пользователя)
        return False

    @admin.display(description="Название (HTML)")
    def title_preview(self, obj):
        if obj and obj.s_title:
            return mark_safe(unescape(obj.s_title))
        return "—"

    @admin.display(description="Превью SVG")
    def svg_preview(self, obj):
        if obj.file_svg:
            return format_html(
                '<div style="max-width: 280px; max-height: 280px; background: #80808080; padding: 8px; border-radius: 8px;">'
                '<img src="{}" width="100%" />'
                '</div>',
                obj.file_svg.url,
            )
        return "Нет файла"

    @admin.display(description="Размер файла")
    def file_size_display(self, obj):
        if obj and obj.file_svg:
            try:
                size_bytes = obj.file_svg.size
                if size_bytes >= 1024 * 1024:
                    return f"{size_bytes / (1024 * 1024):.2f} МБ"
                elif size_bytes >= 1024:
                    return f"{size_bytes / 1024:.1f} КБ"
                return f"{size_bytes} Б"
            except Exception:
                return "—"
        return "—"


# ----
# АДМИНКА ЛАЙКОВ/ДИСЛАЙКОВ (все только на просмотр)
@admin.register(TbVote)
class TbVoteAdmin(admin.ModelAdmin):
    """
    Просмотр анонимного журнала голосов и отпечатков (только для чтения).
    """
    list_display = ("id", "k_item", "i_direction", "fingerprint_short", "d_created_at")
    list_filter = ("i_direction", "d_created_at")
    search_fields = ("s_fingerprint", "k_item__s_hash_id", "k_item__s_title")
    readonly_fields = ("id", "k_item", "i_direction", "s_fingerprint", "d_created_at")
    ordering = ("-d_created_at",)

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    @admin.display(description="Отпечаток (хэш)")
    def fingerprint_short(self, obj):
        return f"{obj.s_fingerprint[:12]}..."


# ----
# АДМИНКА БЛОГА
# Кастомная форма
class BlogPostAdminForm(CodeMirrorFormMixin):
    """
    Кастомная форма для админки потов в блог (TbBlogPost).
    Добавляет виджеты CodeMirror для текстовых полей.
    """
    # Виртуальные поля для настройки типографа
    etp_enable = forms.BooleanField(
        label="Включить типограф",
        initial=False,
        required=False,
        help_text="Включить автоматическую типографику для HTML полей (заголовок, тизер, контент)&nbsp;&nbsp;&nbsp;"
    )
    etp_language = forms.ChoiceField(
        label="Язык типографики",
        choices=[('ru', 'Русский'), ('en', 'English'), ('ru,en', 'Ru + En')],
        initial='ru',
        required=False
    )
    etp_quotes = forms.BooleanField(
        label="Кавычки",
        initial=True,
        required=False,
        help_text="Заменять кавычки<br/>(«ёлочки» для русского, “лапки” для английского)&nbsp;&nbsp;&nbsp;"
    )
    etp_hyphenation = forms.BooleanField(
        label="Расставлять переносы",
        initial=True,
        required=False,
        help_text="Расставлять мягкие переносы (&amp;shy;)&nbsp;&nbsp;&nbsp;<br/>"
                  "в словах длиннее <b>14</b> символов&nbsp;&nbsp;&nbsp;"
    )
    etp_sanitize = forms.BooleanField(
        label="Очистка HTML",
        initial=False,
        required=False,
        help_text="Удалять весь HTML из исходного текста&nbsp;&nbsp;&nbsp;"
    )
    etp_hanging_punctuation = forms.BooleanField(
        label="Висячая пунктуация",
        initial=False,
        required=False,
        help_text="Выносить пунктуацию в начало строк<br/>&nbsp;&nbsp;&nbsp;"
                  "(только для заголовков... для тизера и контента отключается автоматически)&nbsp;&nbsp;&nbsp;"
    )
    etp_mode = forms.ChoiceField(
        label="Режим вывода",
        choices=[('mixed', 'Смешанный (Mixed)'), ('unicode', 'Юникод (Unicode)'), ('mnemonic', 'Мнемоники')],
        initial='mixed',
        required=False,
        help_text="Формат спецсимволов (например, кавычек, тире, многоточий) в&nbsp;HTML: смешанный, юникод"
                  "&nbsp;или мнемоники&nbsp;&nbsp;&nbsp;"
    )

    class Meta:
        model = TbBlogPost
        fields = (
            # Виртуальные поля для настройки типографа
            'etp_enable', 'etp_language', 'etp_quotes', 'etp_hyphenation', 'etp_sanitize',
            'etp_hanging_punctuation', 'etp_mode',
            # Остальные поля модели TbArticle
            's_title', 'slug', 's_teaser', 's_content', 'f_cover_img',
            'is_published', 'd_published_at',
        )

    def __init__(self, *args, **kwargs):
        """
        При инициализации формы подгружаем CodeMirror редактор.
        Получаем request из kwargs, переданных из get_form_kwargs в AdminClass.
        """
        # Извлекаем request из kwargs если он есть
        self.request = kwargs.pop('request', None)

        super().__init__(*args, **kwargs)

        # Конфигурируем поля для CodeMirror
        self.setup_codemirror_field('s_title', language='text',
                                    css_class='codemirror-width-l codemirror-no-lines')
        self.setup_codemirror_field('slug', language='text',
                                    css_class='codemirror-width-l codemirror-no-lines')
        self.setup_codemirror_field('s_teaser', language='html',
                                    css_class='codemirror-width-xl codemirror-min-height-5')
        self.setup_codemirror_field('s_content', language='html',
                                    css_class='codemirror-width-xl codemirror-min-height-10')

# Конфигурация админки
@admin.register(TbBlogPost)
class TbBlogPostAdmin(RequestInFormMixin, admin.ModelAdmin):
    """
    Управление статьями блога, документацией и инфо-страницами (HTML + etpgrf).
    """
    form = BlogPostAdminForm

    list_display = ("id", "article_thumbnail", "s_title_display", "slug", "is_published", "d_published_at", "d_created_at")
    list_display_links = ("id", "s_title_display")
    list_filter = ("is_published", "d_published_at", "d_created_at")
    search_fields = ("s_title", "slug", "s_teaser", "s_content")
    prepopulated_fields = {"slug": ("s_title",)}
    readonly_fields = ("id", "d_created_at", "d_updated_at")
    fieldsets = (
        ("Атрибуты публикации", {
            "fields": ("is_published", "slug", "d_published_at", )
        }),
        ("Основные поля", {
            "fields": ("s_title", "f_cover_img", "s_teaser", "s_content", ),
            "description": "В полях допускается HTML, поддерживается чистая верстка, настройки типографа etpgrf в"
                           " следующем блоке.",
        }),
        ('Типограф', {
            'fields': (('etp_enable',), ('etp_language', 'etp_mode'),
                       ('etp_quotes', 'etp_hyphenation', 'etp_sanitize', 'etp_hanging_punctuation')),
            # 'classes': ('collapse',),
            'description': 'Типограф применяется при сохранении и срабатывает на HTML-поля (ЗАГОЛОВОК, ТИЗЕР СТАТЬИ'
                           ' и СТАТЬЯ). Если выключить — HTML будет сохранен без изменений.',
        }),
        ("Системные даты", {
            "fields": ("id", "d_created_at", "d_updated_at", ),
            "classes": ("collapse",),
        }),
    )

    @admin.display(description="Обложка")
    def article_thumbnail(self, obj):
        """
        Отображает миниатюру изображения статьи в списке (аккуратный квадрат 36x36 px).
        Работает со стандартным ImageField (f_cover_img) без внешних библиотек.
        """
        if obj and obj.f_cover_img:
            try:
                return format_html(
                    '<img src="{}" width="20" height="20" style="border: 1px solid silver;" title="{}" alt="" />',
                    obj.f_cover_img.url,
                    obj.s_title,
                )
            except Exception:
                return mark_safe('<span style="color: #999">(ошибка)</span>')

        return mark_safe(
            '<img width="20" height="20" style="border: 1px solid silver; background: #90909060;" title="Нет картинки" alt="" />'
        )

    def save_model(self, request, obj, form, change):
        """
        Переопределяем save_model для применения:
         1. Tипографа etpgrf для полей s_title, s_teaser и s_content
         2. Генерации Slug c транслитерацией

        Args:
            request: HTTP-запрос (содержит info о пользователе)
            obj: инстанция TbArticle для сохранения
            form: валидированная форма
            change: True если редактирование, False если создание
        """
        # 1. ТИПОГРАФ ETPGRF
        # Проверяем, включен ли типограф
        if form.cleaned_data.get('etp_enable', True):
            # Получаем все настройки из формы
            langs = form.cleaned_data.get('etp_language', 'ru').split(',')

            # 1.1. LayoutProcessor: включаем layout с базовыми настройками
            layout_option = etpgrf.LayoutProcessor(
                langs=langs,
                process_initials_and_acronyms=True,
                process_units=True
            )

            # 1.2. Hyphenator (переносы слов)
            hyphenation_option = False
            if form.cleaned_data.get('etp_hyphenation', True):
                hyphenation_option = etpgrf.Hyphenator(
                    langs=langs,
                    max_unhyphenated_len=14
                )

            # 1.3. Sanitizer (очистка HTML перед типографированием)
            # Режимы: 'html' (удаляет все теги), 'etp' (только висячая пунктуация), None/False (ничего не делает)
            if form.cleaned_data.get('etp_sanitize', True):
                sanitizer_option = 'html'  # Удаляет все HTML-теги
            else:
                sanitizer_option = False  # Санитайзер отключен

            # 1.4. Базовые настройки типографа (используются для всех полей)
            base_options = {
                'langs': langs,
                'process_html': True,
                'quotes': form.cleaned_data.get('etp_quotes', True),
                'layout': layout_option,
                'unbreakables': True,
                'hyphenation': hyphenation_option,
                'sanitizer': sanitizer_option,
                'symbols': True,
                'mode': form.cleaned_data.get('etp_mode', 'mixed'),
            }

            # 1.5. Для заголовков: висячая пунктуация может быть включена
            options_title = {
                **base_options,
                'hanging_punctuation': form.cleaned_data.get('etp_hanging_punctuation', True),
            }
            t_title = etpgrf.Typographer(**options_title)
            if obj.s_title:
                obj.s_title = t_title.process(obj.s_title)

            # 1.6. Для тизера и контента: висячая пунктуация всегда отключена
            options_body = {
                **base_options,
                'hanging_punctuation': False,
            }
            t_body = etpgrf.Typographer(**options_body)
            if obj.s_teaser:
                obj.s_teaser = t_body.process(obj.s_teaser)
            if obj.s_content:
                obj.s_content = t_body.process(obj.s_content)

        # 2. SLUG
        if not obj.slug:
            # 2.0. Если вдруг нет заголовка, то генерируем случайный slug
            if not obj.s_title:
                obj.slug = f"title-{random.randint(1, 4095):03x}"
            else:
                # 2.1. Очищаем текст от HTML и спецсимволов через вспомогательную функцию
                plain_title = clean_html_to_plain_text(obj.s_title)

                # 2.2. Транслитерируем и создаем slug (pytils подходит для русского)
                obj.slug = pytils.translit.slugify(plain_title) if plain_title else ""

                # 2.3. Нормализуем множественные дефисы, удаляем дефисы в начале/конце
                obj.slug = re.sub(pattern=r"-+", repl="-", string=obj.slug).strip("-")

                # 2.4. Если все еще нет slug (например заголовок из спец-символов) — генерируем
                obj.slug = obj.slug or f"title-{random.randint(1, 4095):03x}"

        # 3. Вызываем родительский save_model который вызовет obj.save()
        super().save_model(request, obj, form, change)

    @admin.display(description="Заголовок")
    def s_title_display(self, obj):
        # Отображаем HTML-заголовок статьи как безопасный HTML
        if obj and obj.s_title:
            return mark_safe(unescape(obj.s_title))
        return "—"
