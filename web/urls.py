from django.urls import path

from web import views

app_name = "web"

urlpatterns = [
    path("", views.Home.as_view(), name="home"),
    path("market/", views.Market.as_view(), name="market"),
    path("market/<int:pk>/", views.ProductoDetalle.as_view(), name="producto_detalle"),
]
