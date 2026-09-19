from django.contrib.auth.views import LoginView, LogoutView
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

    # Cuenta de proveedor (autoservicio, documento de membresías sección 19).
    path("cuenta/registro/", views.RegistroProveedor.as_view(), name="cuenta_registro"),
    path(
        "cuenta/ingresar/",
        LoginView.as_view(template_name="web/cuenta_login.html", redirect_authenticated_user=True),
        name="cuenta_login",
    ),
    path("cuenta/salir/", LogoutView.as_view(next_page="web:home"), name="cuenta_logout"),
    path("cuenta/", views.MiEmpresa.as_view(), name="cuenta_empresa"),
    path("cuenta/productos/", views.MisProductosLista.as_view(), name="cuenta_productos"),
    path("cuenta/productos/nuevo/", views.MisProductosCrear.as_view(), name="cuenta_productos_add"),
    path("cuenta/productos/<int:pk>/", views.MisProductosEditar.as_view(), name="cuenta_productos_edit"),
    path(
        "cuenta/productos/<int:pk>/eliminar/",
        views.MisProductosEliminar.as_view(), name="cuenta_productos_del",
    ),
    path("cuenta/membresia/", views.MiMembresia.as_view(), name="cuenta_membresia"),
]
