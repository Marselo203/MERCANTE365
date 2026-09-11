from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path

admin.site.site_header = "MERCANTE365 — desarrollo"
admin.site.site_title = "Admin de desarrollo"
admin.site.index_title = "Administración (solo desarrollo)"

urlpatterns = [
    path("", include("web.urls")),
    path("panel/", include("panel.urls")),
    # Admin de Django: solo para desarrollo.
    path("django-admin/", admin.site.urls),
]

# Solo en desarrollo y solo si las imágenes están en disco local. En producción
# las sirve nginx o el Object Storage.
if settings.DEBUG and not settings.USAR_OBJECT_STORAGE:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
