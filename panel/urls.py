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
        "descripcion": "Todas las empresas registradas, proveedoras y compradoras. Una "
        "proveedora recién se muestra como verificada en el catálogo cuando le cambiás el "
        "estado a «Aprobada».",
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
        "slug": "proveedor", "model": Empresa, "filtro": {"rol": Empresa.Rol.PROVEEDORA},
        "etiqueta": "proveedor", "etiqueta_plural": "proveedores",
        "descripcion": "Solo las empresas proveedoras. Cambiá el estado a «Aprobada» para "
        "que se muestren como verificadas en el catálogo.",
        "form_fields": [
            "razon_social", "nombre_comercial", "identificador_tributario",
            "slug", "pais", "region", "ciudad", "direccion_fisica", "descripcion",
            "estado_verificacion",
        ],
        "columnas": [
            ("razon_social", "Razón social"),
            ("get_estado_verificacion_display", "Verificación"), ("ciudad", "Ciudad"),
        ],
    },
    {
        "slug": "comprador", "model": Empresa, "filtro": {"rol": Empresa.Rol.COMPRADORA},
        "etiqueta": "comprador", "etiqueta_plural": "compradores",
        "descripcion": "Las empresas que envían requerimientos desde el catálogo público.",
        "form_fields": [
            "razon_social", "nombre_comercial", "identificador_tributario",
            "slug", "pais", "region", "ciudad", "direccion_fisica", "descripcion",
        ],
        "columnas": [
            ("razon_social", "Razón social"), ("ciudad", "Ciudad"),
        ],
    },
    {
        "slug": "calificacion", "model": Empresa, "filtro": {"rol": Empresa.Rol.PROVEEDORA},
        "sin_alta": True,
        "etiqueta": "calificación de proveedor", "etiqueta_plural": "calificación de proveedores",
        "descripcion": "El proveedor NO puede autodeclararse «calificado»: marcá solo los "
        "criterios que MERCANTE365 revisó de verdad y recién ahí activá «Proveedor "
        "calificado» (documento de producto, secciones 21 y 32).",
        "form_fields": [
            "chk_info_empresarial", "chk_contacto_revisado", "chk_direccion_registrada",
            "chk_sitio_web_revisado", "chk_info_comercial_revisada",
            "chk_producto_info_disponible", "chk_producto_fotos_disponibles",
            "chk_producto_ficha_tecnica", "chk_producto_marca_identificada",
            "chk_producto_info_comercial",
            "documentacion_estado", "calificado",
        ],
        "columnas": [
            ("razon_social", "Proveedor"), ("progreso_checklist", "Checklist"),
            ("get_documentacion_estado_display", "Documentación"), ("calificado", "Calificado"),
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


# Secciones del Back Office que menciona el documento de producto pero que
# todavía son visión futura (fases posteriores a esta), sin modelo propio
# todavía: muestran una página fija "Próximamente" en vez de un 404.
PROXIMAMENTE = [
    ("catalogos", "Catálogos"),
    ("premium", "Premium"),
    ("premium_plus", "Premium Plus"),
    ("red_comercial", "Red Comercial"),
    ("oportunidades", "Oportunidades"),
    ("ventas", "Ventas"),
    ("comisiones", "Comisiones"),
    ("configuracion", "Configuración"),
]

# Orden del menú del Back Office tal como lo describe el documento de
# producto: mezcla los recursos reales de arriba con las secciones
# "Próximamente". Cada entrada es (tipo, slug) o (tipo, slug, etiqueta) para
# pisar la etiqueta del recurso solo en el menú (ej. "requerimiento" se
# etiqueta acá "Leads / RFQ", tal como lo nombra el documento).
MENU = [
    ("recurso", "empresa"),
    ("recurso", "proveedor"),
    ("recurso", "producto"),
    ("recurso", "categoria"),
    ("proximamente", "catalogos"),
    ("recurso", "calificacion", "Calificación"),
    ("proximamente", "premium"),
    ("proximamente", "premium_plus"),
    ("proximamente", "red_comercial"),
    ("recurso", "requerimiento", "Leads / RFQ"),
    ("proximamente", "oportunidades"),
    ("proximamente", "ventas"),
    ("proximamente", "comisiones"),
    ("recurso", "comprador"),
    ("proximamente", "configuracion"),
]


def _crud(r):
    """`sin_alta` (opcional): la vista es una lista angosta sobre un modelo que
    ya se gestiona completo desde otro recurso (ej. «calificación» es un
    subconjunto de campos de `Empresa`) — no tiene sentido crear ni eliminar
    desde ahí, solo listar y editar esos campos."""
    s = r["slug"]
    r = dict(r, url_list=f"panel:{s}_list", url_edit=f"panel:{s}_edit")
    urls = [
        path(f"{s}/", views.Lista.as_view(recurso=r), name=f"{s}_list"),
        path(f"{s}/<int:pk>/", views.Editar.as_view(recurso=r), name=f"{s}_edit"),
    ]
    if not r.get("sin_alta"):
        r["url_add"] = f"panel:{s}_add"
        r["url_del"] = f"panel:{s}_del"
        urls.append(path(f"{s}/nuevo/", views.Crear.as_view(recurso=r), name=f"{s}_add"))
        urls.append(path(f"{s}/<int:pk>/eliminar/", views.Eliminar.as_view(recurso=r), name=f"{s}_del"))
    return urls


urlpatterns = [
    path("ingresar/", LoginView.as_view(template_name="panel/login.html"), name="login"),
    path("salir/", LogoutView.as_view(), name="logout"),
    path("", views.Dashboard.as_view(), name="dashboard"),
]
for _r in RECURSOS:
    urlpatterns += _crud(_r)
for _slug, _etiqueta in PROXIMAMENTE:
    urlpatterns.append(
        path(
            f"proximamente/{_slug}/",
            views.Proximamente.as_view(titulo=_etiqueta),
            name=f"proximamente_{_slug}",
        )
    )
