"""
Карты сайта (Sitemaps) для поисковой индексации HypnoSVG.
"""
from django.contrib.sitemaps import Sitemap
from django.urls import reverse

from .models import TbHypn0Item


class StaticViewSitemap(Sitemap):
    """
    Карта сайта для ключевых страниц и разделов интерфейса.
    """
    changefreq = "daily"

    def items(self):
        return [
            ("hypn0_site:index", 1.0, "daily"),
            ("hypn0_site:gallery_archive", 0.9, "daily"),
        ]

    def location(self, item):
        return reverse(item[0])

    def priority(self, item):
        return item[1]

    def changefreq(self, item):
        return item[2]


class GalleryItemSitemap(Sitemap):
    """
    Карта сайта для публичных гипно-картин галереи сообщества.
    """
    changefreq = "weekly"

    def items(self):
        # Включаем только публичные картины, исключая подозрительные/заблокированные
        return (
            TbHypn0Item.objects.filter(is_public=True)
            .exclude(i_level__in=[TbHypn0Item.Level.SHAMED, TbHypn0Item.Level.SUSPICIOUS])
            .order_by("-d_created_at")
        )

    def lastmod(self, obj: TbHypn0Item):
        return obj.d_created_at

    def priority(self, obj: TbHypn0Item):
        # Динамический приоритет в зависимости от уровня признания в психо-матрице
        if obj.i_level == TbHypn0Item.Level.IMMORTAL:
            return 0.9
        elif obj.i_level == TbHypn0Item.Level.LEVEL_2:
            return 0.8
        elif obj.i_level == TbHypn0Item.Level.LEVEL_1:
            return 0.7
        return 0.6

    def location(self, obj: TbHypn0Item):
        return obj.get_absolute_url()


sitemaps = {
    "static": StaticViewSitemap,
    "gallery": GalleryItemSitemap,
}
