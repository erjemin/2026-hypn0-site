from django.apps import AppConfig


class Hypn0SiteConfig(AppConfig):
    name = 'hypn0_site'
    verbose_name = 'Сайт Hypn0'

    def ready(self) -> None:
        """Инициализация Django Admin с кастомным заголовком и названиями."""
        from django.contrib import admin
        admin.site.site_header = 'Управление HYPN0'
        admin.site.site_title = 'Hypn0 Administrator'
        admin.site.index_title = 'Добро пожаловать в Hypn0'
