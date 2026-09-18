from django.urls import path

from web import views

app_name = "web"

urlpatterns = [
    path("", views.Home.as_view(), name="home"),
    path("quienes-somos/", views.QuienesSomos.as_view(), name="quienes_somos"),
    path("como-funciona/", views.ComoFunciona.as_view(), name="como_funciona"),
    path("planes/", views.Planes.as_view(), name="planes"),
    path("market/", views.Market.as_view(), name="market"),
    path("market/<int:pk>/", views.ProductoDetalle.as_view(), name="producto_detalle"),
    path("proveedores/<slug:slug>/", views.PerfilProveedor.as_view(), name="perfil_proveedor"),
]
