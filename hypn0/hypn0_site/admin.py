from django.contrib import admin

from .models import BlogPost, HalftoneItem, HalftoneVote


@admin.register(HalftoneItem)
class HalftoneItemAdmin(admin.ModelAdmin):
    list_display = (
        "hash_id",
        "title",
        "likes_count",
        "views_count",
        "score",
        "is_curated",
        "is_public",
        "created_at",
    )
    list_filter = (
        "is_curated",
        "is_public",
        "created_at",
    )
    search_fields = (
        "hash_id",
        "title",
        "promo_title",
    )
    readonly_fields = (
        "created_at",
        "score",
        "file_size",
    )


@admin.register(HalftoneVote)
class HalftoneVoteAdmin(admin.ModelAdmin):
    list_display = (
        "item",
        "fingerprint",
        "created_at",
    )
    list_filter = ("created_at",)
    search_fields = (
        "item__hash_id",
        "item__title",
        "fingerprint",
    )
    readonly_fields = ("created_at",)


@admin.register(BlogPost)
class BlogPostAdmin(admin.ModelAdmin):
    list_display = (
        "title",
        "slug",
        "is_published",
        "published_at",
        "created_at",
    )
    list_filter = (
        "is_published",
        "published_at",
    )
    search_fields = (
        "title",
        "slug",
        "summary",
        "content",
    )
    prepopulated_fields = {"slug": ("title",)}
    readonly_fields = (
        "created_at",
        "updated_at",
    )
