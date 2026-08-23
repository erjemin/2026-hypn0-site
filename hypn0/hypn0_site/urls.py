from django.urls import path

from hypn0 import settings
from . import views

app_name = "hypn0_site"

urlpatterns = [
    path("", views.index, name="index"),
    path("generate", views.generate, name="generate"),
]

if settings.DEBUG:
    urlpatterns += [path("tmp/", views.tmp, name="web_tmp")]
