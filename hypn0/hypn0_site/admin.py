# Кастомная конфигурация Django Admin для Hypn0.
# Регистрируем модели с удобным интерфейсом.

from django import forms
from django.contrib import admin
from django.forms import Textarea
from django.utils.html import format_html
from .models import (
    TbHypn0Item,
    TbVote,
    TbBlogPost
)

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

    def get_form(self, request, obj=None, **kwargs):
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


@admin.register(TbHypn0Item)
class TbHypn0ItemAdmin(admin.ModelAdmin):
    """
    Панель управления гипно-картинами (модерация, просмотр статистики, редактирование).
    Создание новых картин через админку заблокировано (создание только на фронтенде).
    """
    list_display = (
        "id",
        "s_hash_id",
        "title_preview",
        "i_level",
        "i_likes_count",
        "i_claims_count",
        "i_views_count",
        "f_score",
        "is_public",
        "d_created_at",
    )
    list_display_links = ("id", "s_hash_id", "title_preview")
    list_filter = ("i_level", "is_public", "d_created_at")
    search_fields = ("s_hash_id", "s_title", "s_promo_title", "s_promo_url")
    readonly_fields = (
        "id",
        "s_hash_id",
        "i_file_size",
        "i_likes_count",
        "i_views_count",
        "i_claims_count",
        "i_promo_clicks",
        "d_created_at",
        "d_updated_at",
        "svg_preview",
    )
    fieldsets = (
        (
            "Основная информация",
            {
                "fields": (
                    "id",
                    "s_hash_id",
                    "s_title",
                    "file_svg",
                    "svg_preview",
                    "i_file_size",
                    "is_public",
                )
            },
        ),
        (
            "Модерация и Smart Retention",
            {
                "fields": (
                    "i_level",
                    "f_score",
                ),
                "description": "Уровень модерации и рейтинг 'гравитации' для ротации и очистки хранилища.",
            },
        ),
        (
            "Метрики популярности",
            {
                "fields": (
                    "i_likes_count",
                    "i_claims_count",
                    "i_views_count",
                ),
            },
        ),
        (
            "Промо-блок (Спонсоры и Авторы)",
            {
                "fields": (
                    "s_promo_url",
                    "s_promo_title",
                    "i_promo_clicks",
                ),
                "classes": ("collapse",),
            },
        ),
        (
            "Метаданные генерации",
            {
                "fields": ("j_metadata",),
                "classes": ("collapse",),
            },
        ),
        (
            "Временные метки",
            {
                "fields": ("d_created_at", "d_updated_at"),
                "classes": ("collapse",),
            },
        ),
    )

    def has_add_permission(self, request):
        # Создание картин возможно только с фронтенда (требуется обработка растра и согласие пользователя)
        return False

    @admin.display(description="Название (HTML)")
    def title_preview(self, obj):
        return format_html(obj.s_title)

    @admin.display(description="Превью SVG")
    def svg_preview(self, obj):
        if obj.file_svg:
            return format_html(
                '<div style="max-width: 250px; max-height: 250px; background: #1e293b; padding: 8px; border-radius: 8px;">'
                '<img src="{}" style="max-width: 100%; max-height: 230px;" />'
                '</div>',
                obj.file_svg.url,
            )
        return "Нет файла"


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


@admin.register(TbBlogPost)
class TbBlogPostAdmin(admin.ModelAdmin):
    """
    Управление статьями блога, документацией и инфо-страницами (HTML + etpgrf).
    """
    list_display = ("id", "s_title_display", "slug", "is_published", "d_published_at", "d_created_at")
    list_display_links = ("id", "s_title_display")
    list_filter = ("is_published", "d_published_at", "d_created_at")
    search_fields = ("s_title", "slug", "s_teaser", "s_content")
    prepopulated_fields = {"slug": ("s_title",)}
    readonly_fields = ("id", "d_created_at", "d_updated_at")
    fieldsets = (
        (
            "Публикация",
            {
                "fields": (
                    "is_published",
                    "d_published_at",
                )
            },
        ),
        (
            "Заголовок и URL",
            {
                "fields": (
                    "s_title",
                    "slug",
                    "f_cover_img",
                )
            },
        ),
        (
            "Контент статьи (HTML + etpgrf)",
            {
                "fields": (
                    "s_teaser",
                    "s_content",
                ),
                "description": "HTML-текст, типографированный etpgrf. Поддерживается чистая верстка.",
            },
        ),
        (
            "Системные даты",
            {
                "fields": (
                    "id",
                    "d_created_at",
                    "d_updated_at",
                ),
                "classes": ("collapse",),
            },
        ),
    )

    @admin.display(description="Заголовок")
    def s_title_display(self, obj):
        return format_html(obj.s_title)
