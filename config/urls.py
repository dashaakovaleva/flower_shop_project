from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path

admin.site.site_header = "FloraIS — административная панель"
admin.site.site_title = "FloraIS"
admin.site.index_title = "Управление информационной системой"

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/", include("shop.api_urls")),
    path("", include("shop.urls")),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
