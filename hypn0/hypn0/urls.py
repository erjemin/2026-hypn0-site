"""
URL configuration for hypn0 project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/6.0/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import include, path
from django.conf.urls.static import static
from . import settings

urlpatterns = [
    # Админ-сайт с переименованными приложениями (переопределен в frontend/apps.py)
    path(settings.ADMIN_URL, admin.site.urls),
    path('', include('hypn0_site.urls')),
]

if settings.DEBUG:
    import mimetypes
    import debug_toolbar
    from django.views.static import serve

    def _serve_public_root_file(request, path):
        """Отдаёт файлы из корня `public` в dev-режиме в utf-8."""
        response = serve(request, path, document_root=settings.PUBLIC_DIR)
        content_type, _ = mimetypes.guess_type(path)
        if content_type:
            if content_type.startswith('text/'):
                response['Content-Type'] = f'{content_type}; charset=utf-8'
            else:
                response['Content-Type'] = content_type
        elif path.endswith('.txt'):
            response['Content-Type'] = 'text/plain; charset=utf-8'
        elif path.endswith('.html'):
            response['Content-Type'] = 'text/html; charset=utf-8'
        return response

    def _iter_public_root_files():
        """Находит все обычные файлы в корне `public`, кроме служебных артефактов."""
        for file_path in sorted(settings.PUBLIC_DIR.iterdir()):
            if not file_path.is_file():
                continue
            if file_path.name.startswith('.'):
                continue
            if file_path.name == 'README.md':
                continue
            yield file_path.name

    PUBLIC_ROOT_URLPATTERNS = [
        path(filename, _serve_public_root_file, {'path': filename})
        for filename in _iter_public_root_files()
    ]

    urlpatterns = [path('__debug__/', include(debug_toolbar.urls)), ] + urlpatterns
    urlpatterns = [*PUBLIC_ROOT_URLPATTERNS, *urlpatterns]
    urlpatterns += static(settings.STATIC_URL, document_root=settings.PUBLIC_DIR.joinpath('static'))
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
