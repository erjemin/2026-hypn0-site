from django.urls import path

from hypn0 import settings
from . import views

app_name = "hypn0_site"

urlpatterns = [
    path("", views.index, name="index"),
    path("generate", views.generate, name="generate"),
    path("publish", views.publish, name="publish"),
    path("gallery/random", views.gallery_random, name="gallery_random"),
    path("gallery/random-pool", views.gallery_random, name="gallery_random_pool"),
    path("gallery/floor/<slug:floor_slug>", views.gallery_floor, name="gallery_floor"),
    path("gallery/<str:hash_id>", views.gallery_detail, name="gallery_detail"),
    path("gallery/<str:hash_id>/download", views.gallery_download, name="gallery_download"),
    path("gallery/<str:hash_id>/vote", views.gallery_vote, name="gallery_vote"),
]

if settings.DEBUG:
    urlpatterns += [path("tmp/", views.tmp, name="web_tmp")]
