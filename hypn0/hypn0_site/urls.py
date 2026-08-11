from django.urls import path

from . import views
from hypn0 import settings

app_name = "hypn0_site"

urlpatterns = [
    path("", views.index, name="index"),
]


if settings.DEBUG:
    urlpatterns += [path('tmp/', views.tmp, name='web_tmp')]