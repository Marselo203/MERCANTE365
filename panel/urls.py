from django.contrib.auth.views import LoginView, LogoutView
from django.urls import path

from catalogo.models import (
    AtributoDefinicion,
    Categoria,
    ContactoEmpresa,
    Empresa,
    EscalaPrecio,
    ImagenProducto,
    Producto,
    Requerimiento,
)
from panel import views

app_name = "panel"

# Un recurso por modelo editable. `form_fields` = orden del formulario;
# `columnas` = (atributo_o_método, encabezado) de la tabla de listado;
# `descripcion` = el texto de ayuda que se muestra arriba de esa tabla.
RECURSOS = [
    {
        "slug": "producto", "model": Producto,
        "etiqueta": "producto", "etiqueta_plural": "productos",
        "descripcion": "El catálogo: cada fila es un producto de alguna empresa proveedora. "
        "Marcá «Publicado» para que se vea en el sitio, y «Verificado» cuando confirmaste "
        "sus datos con el proveedor.",
        "form_fields": [
            "empresa", "categoria", "nombre", "slug", "sku", "descripcion_tecnica",
            "precio_unitario", "moneda", "cantidad_minima_pedido", "unidad_empaque",
            "plazo_entrega_dias", "stock_disponible", "atributos",
            "verificado", "publicado", "destacado",
        ],
        "columnas": [
            ("nombre", "Nombre"), ("empresa", "Empresa"), ("categoria", "Categoría"),
            ("precio_unitario", "Precio"), ("publicado", "Publicado"),
            ("verificado", "Verificado"),
        ],
    },
    {
        "slug": "empresa", "model": Empresa,
        "etiqueta": "empresa", "etiqueta_plural": "empresas",
        "descripcion": "Empresas proveedoras (venden productos) y compradoras (envían "
        "requerimientos). Una proveedora recién se muestra como verificada en el catálogo "
        "cuando le cambiás el estado a «Aprobada».",
        "form_fields": [
            "rol", "razon_social", "nombre_comercial", "identificador_tributario",
            "slug", "pais", "region", "ciudad", "direccion_fisica", "descripcion",
            "estado_verificacion",
        ],
        "columnas": [
            ("razon_social", "Razón social"), ("get_rol_display", "Rol"),
            ("get_estado_verificacion_display", "Verificación"), ("ciudad", "Ciudad"),
        ],
    },
    {
        "slug": "categoria", "model": Categoria,
        "etiqueta": "categoría", "etiqueta_plural": "categorías",
        "descripcion": "Los rubros del catálogo, organizados en árbol: una categoría puede "
        "tener subcategorías. Es lo que los visitantes usan para filtrar el catálogo público.",
        "form_fields": ["padre", "nombre", "slug"],
        "columnas": [("__str__", "Ruta"), ("slug", "Slug")],
    },
    {
        "slug": "atributo", "model": AtributoDefinicion,
        "etiqueta": "definición de atributo", "etiqueta_plural": "definiciones de atributo",
        "descripcion": "Las características técnicas que se piden para los productos de cada "
        "categoría (ej. «puertos» o «velocidad» para switches). Las subcategorías las heredan.",
        "form_fields": [
            "categoria", "clave", "etiqueta", "tipo", "unidad", "opciones",
            "obligatorio", "orden",
        ],
        "columnas": [
            ("etiqueta", "Etiqueta"), ("clave", "Clave"), ("categoria", "Categoría"),
            ("get_tipo_display", "Tipo"), ("obligatorio", "Obligatorio"),
        ],
    },
    {
        "slug": "imagen", "model": ImagenProducto,
        "etiqueta": "imagen", "etiqueta_plural": "imágenes de producto",
        "descripcion": "Las fotos de cada producto. Marcá una sola como «Principal»: es la "
        "que se muestra primero en el catálogo y en las tarjetas del sitio.",
        "form_fields": ["producto", "imagen", "alt", "es_principal", "orden"],
        "columnas": [
            ("producto", "Producto"), ("alt", "Alt"), ("es_principal", "Principal"),
            ("orden", "Orden"),
        ],
    },
    {
        "slug": "escala", "model": EscalaPrecio,
        "etiqueta": "escala de precio", "etiqueta_plural": "escalas de precio",
        "descripcion": "Precios por volumen: a partir de cierta cantidad, un producto puede "
        "tener un precio distinto al de lista.",
        "form_fields": ["producto", "volumen_minimo", "precio_unitario"],
        "columnas": [
            ("producto", "Producto"), ("volumen_minimo", "Desde"),
            ("precio_unitario", "Precio"),
        ],
    },
    {
        "slug": "contacto", "model": ContactoEmpresa,
        "etiqueta": "contacto", "etiqueta_plural": "contactos de empresa",
        "descripcion": "Las personas de contacto de cada empresa. El contacto marcado como "
        "«Principal» es el que ve el comprador en la ficha del producto.",
        "form_fields": ["empresa", "nombre", "cargo", "email", "telefono", "es_principal"],
        "columnas": [
            ("empresa", "Empresa"), ("nombre", "Nombre"), ("email", "Email"),
            ("es_principal", "Principal"),
        ],
    },
    {
        "slug": "requerimiento", "model": Requerimiento,
        "etiqueta": "requerimiento", "etiqueta_plural": "requerimientos",
        "descripcion": "Los pedidos de información que los compradores enviaron desde el "
        "catálogo público. Cambiá el «Estado» para llevar el seguimiento de cada uno.",
        "form_fields": [
            "producto", "nombre_contacto", "email_contacto", "telefono_contacto",
            "empresa_compradora", "volumen_requerido", "plazo_esperado", "observaciones", "estado",
        ],
        "columnas": [
            ("producto", "Producto"), ("nombre_contacto", "Contacto"),
            ("email_contacto", "Email"), ("get_estado_display", "Estado"), ("creado", "Fecha"),
        ],
    },
]


def _crud(r):
    s = r["slug"]
    r = dict(
        r,
        url_list=f"panel:{s}_list", url_add=f"panel:{s}_add",
        url_edit=f"panel:{s}_edit", url_del=f"panel:{s}_del",
    )
    return [
        path(f"{s}/", views.Lista.as_view(recurso=r), name=f"{s}_list"),
        path(f"{s}/nuevo/", views.Crear.as_view(recurso=r), name=f"{s}_add"),
        path(f"{s}/<int:pk>/", views.Editar.as_view(recurso=r), name=f"{s}_edit"),
        path(f"{s}/<int:pk>/eliminar/", views.Eliminar.as_view(recurso=r), name=f"{s}_del"),
    ]


urlpatterns = [
    path("ingresar/", LoginView.as_view(template_name="panel/login.html"), name="login"),
    path("salir/", LogoutView.as_view(), name="logout"),
    path("", views.Dashboard.as_view(), name="dashboard"),
]
for _r in RECURSOS:
    urlpatterns += _crud(_r)
