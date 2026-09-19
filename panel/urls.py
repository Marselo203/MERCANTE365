from django.contrib.auth.views import LoginView, LogoutView
from django.urls import path

from catalogo.models import (
    AtributoDefinicion,
    Categoria,
    Comision,
    ContactoEmpresa,
    Empresa,
    EscalaPrecio,
    ImagenProducto,
    Oportunidad,
    Producto,
    Requerimiento,
    Vendedor,
    VendedorProducto,
    Venta,
)
from panel import views

app_name = "panel"

# Un recurso por modelo editable. `form_fields` = orden del formulario;
# `columnas` = (atributo_o_método, encabezado) de la tabla de listado;
# `descripcion` = el texto de ayuda que se muestra arriba de esa tabla.
RECURSOS = [
    {
        "slug": "producto", "model": Producto, "permiso": "catalogo.change_producto",
        "etiqueta": "producto", "etiqueta_plural": "productos",
        "descripcion": "El catálogo: cada fila es un producto de alguna empresa proveedora. "
        "Marcá «Publicado» para que se vea en el sitio (respeta el límite de productos activos "
        "del plan de la empresa), y pasá «Estado de verificación» a Verificado cuando "
        "confirmaste sus datos con el proveedor — la insignia pública también necesita que la "
        "empresa tenga plan PYME o superior.",
        "form_fields": [
            "empresa", "categoria", "nombre", "slug", "sku", "descripcion_tecnica",
            "precio_unitario", "moneda", "cantidad_minima_pedido", "unidad_empaque",
            "plazo_entrega_dias", "stock_disponible", "atributos",
            "estado_verificacion", "publicado", "destacado",
        ],
        "columnas": [
            ("nombre", "Nombre"), ("empresa", "Empresa"), ("categoria", "Categoría"),
            ("precio_unitario", "Precio"), ("publicado", "Publicado"),
            ("get_estado_verificacion_display", "Verificación"),
        ],
    },
    {
        "slug": "empresa", "model": Empresa, "permiso": "catalogo.change_empresa",
        "etiqueta": "empresa", "etiqueta_plural": "empresas",
        "descripcion": "Todas las empresas registradas, proveedoras y compradoras. La insignia "
        "«Empresa Verificada» se otorga recién cuando le cambiás el estado a «Verificada» — y "
        "solo se muestra en público si además tiene un plan PYME o superior.",
        "form_fields": [
            "rol", "razon_social", "nombre_comercial", "identificador_tributario",
            "slug", "pais", "region", "ciudad", "direccion_fisica", "descripcion", "logo",
            "estado_verificacion", "nivel_comercial",
        ],
        "columnas": [
            ("razon_social", "Razón social"), ("get_rol_display", "Rol"),
            ("get_estado_verificacion_display", "Verificación"), ("ciudad", "Ciudad"),
        ],
    },
    {
        "slug": "proveedor", "model": Empresa, "filtro": {"rol": Empresa.Rol.PROVEEDORA},
        "permiso": "catalogo.gestionar_proveedores",
        "etiqueta": "proveedor", "etiqueta_plural": "proveedores",
        "descripcion": "Solo las empresas proveedoras. Cambiá el estado a «Verificada» para "
        "otorgar la insignia — solo se muestra en público con plan PYME o superior.",
        "form_fields": [
            "razon_social", "nombre_comercial", "identificador_tributario",
            "slug", "pais", "region", "ciudad", "direccion_fisica", "descripcion", "logo",
            "estado_verificacion", "nivel_comercial",
        ],
        "columnas": [
            ("razon_social", "Razón social"),
            ("get_estado_verificacion_display", "Verificación"),
            ("get_nivel_comercial_display", "Nivel"), ("ciudad", "Ciudad"),
        ],
    },
    {
        "slug": "comprador", "model": Empresa, "filtro": {"rol": Empresa.Rol.COMPRADORA},
        "permiso": "catalogo.gestionar_compradores",
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
        "sin_alta": True, "permiso": "catalogo.gestionar_calificacion",
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
        "slug": "categoria", "model": Categoria, "permiso": "catalogo.change_categoria",
        "etiqueta": "categoría", "etiqueta_plural": "categorías",
        "descripcion": "Los rubros del catálogo, organizados en árbol: una categoría puede "
        "tener subcategorías. Es lo que los visitantes usan para filtrar el catálogo público.",
        "form_fields": ["padre", "nombre", "slug"],
        "columnas": [("__str__", "Ruta"), ("slug", "Slug")],
    },
    {
        "slug": "atributo", "model": AtributoDefinicion,
        "permiso": "catalogo.change_atributodefinicion",
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
        "slug": "imagen", "model": ImagenProducto, "permiso": "catalogo.change_imagenproducto",
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
        "slug": "escala", "model": EscalaPrecio, "permiso": "catalogo.change_escalaprecio",
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
        "slug": "contacto", "model": ContactoEmpresa, "permiso": "catalogo.change_contactoempresa",
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
        "slug": "requerimiento", "model": Requerimiento, "permiso": "catalogo.change_requerimiento",
        "etiqueta": "requerimiento", "etiqueta_plural": "requerimientos",
        "descripcion": "Los pedidos de información que los compradores enviaron desde el "
        "catálogo público. Cambiá el «Estado» para llevar el seguimiento de cada uno. «Origen» "
        "y «Vendedor» se completan solos si el comprador llegó con un link de referido de la "
        "Red Comercial (documento de producto, sección 68, «Bandeja de Leads / RFQ»).",
        "form_fields": [
            "producto", "nombre_contacto", "email_contacto", "telefono_contacto",
            "empresa_compradora", "volumen_requerido", "plazo_esperado", "observaciones",
            "estado", "origen", "vendedor",
        ],
        "columnas": [
            ("producto", "Producto"), ("nombre_contacto", "Contacto"),
            ("email_contacto", "Email"), ("get_estado_display", "Estado"),
            ("get_origen_display", "Origen"), ("vendedor", "Vendedor"), ("creado", "Fecha"),
        ],
    },
    {
        "slug": "vendedor", "model": Vendedor, "permiso": "catalogo.change_vendedor",
        "etiqueta": "vendedor", "etiqueta_plural": "vendedores",
        "descripcion": "Vendedores independientes de la Red Comercial. El «Código de "
        "referencia» se genera solo si lo dejás vacío — es lo que va en su link "
        "(mercante365.com/?ref=CÓDIGO) para que sus requerimientos queden atribuidos a él.",
        "form_fields": [
            "nombre", "whatsapp", "email", "zona", "especialidad", "comision",
            "estado", "codigo_referencia",
        ],
        "columnas": [
            ("nombre", "Nombre"), ("zona", "Zona"), ("codigo_referencia", "Código de referencia"),
            ("comision", "Comisión %"), ("get_estado_display", "Estado"),
        ],
    },
    {
        "slug": "oportunidad", "model": Oportunidad, "permiso": "catalogo.change_oportunidad",
        "etiqueta": "oportunidad", "etiqueta_plural": "oportunidades",
        "descripcion": "El pipeline de venta de un lead (documento de producto, sección 70). "
        "No se crea sola: elegí a mano qué requerimientos pasan a seguimiento formal.",
        "form_fields": ["requerimiento", "estado"],
        "columnas": [
            ("requerimiento", "Requerimiento"), ("get_estado_display", "Estado"),
            ("actualizada", "Actualizada"),
        ],
    },
    {
        "slug": "venta", "model": Venta, "permiso": "catalogo.change_venta",
        "etiqueta": "venta", "etiqueta_plural": "ventas",
        "descripcion": "Registrar una venta concretada (documento de producto, sección 71), "
        "sea que se haya cerrado acá o fuera del sitio. Al guardarla se calcula sola la "
        "comisión del vendedor si el lead vino atribuido a uno (sección 72).",
        "form_fields": ["oportunidad", "monto", "comprobante_externo", "fecha", "observaciones"],
        "querysets": {
            "oportunidad": lambda: Oportunidad.objects.filter(estado=Oportunidad.Estado.GANADA),
        },
        "columnas": [
            ("oportunidad", "Oportunidad"), ("monto", "Monto"), ("fecha", "Fecha"),
        ],
    },
    {
        "slug": "comision", "model": Comision, "sin_alta": True,
        "permiso": "catalogo.change_comision",
        "etiqueta": "comisión", "etiqueta_plural": "comisiones",
        "descripcion": "Se calculan solas al registrar una venta (documento de producto, "
        "sección 73). Acá solo se avanza el «Estado» a medida que se confirma y se paga.",
        "form_fields": ["estado"],
        "columnas": [
            ("vendedor", "Vendedor"), ("producto", "Producto"), ("proveedor", "Proveedor"),
            ("porcentaje", "%"), ("monto", "Comisión"), ("get_estado_display", "Estado"),
        ],
    },
    {
        "slug": "vinculacion", "model": VendedorProducto,
        "permiso": "catalogo.change_vendedorproducto",
        "etiqueta": "vinculación", "etiqueta_plural": "vinculaciones de vendedor",
        "descripcion": "Qué productos puede representar cada vendedor y con qué comisión "
        "(documento de producto, sección 65). El buscador de «Producto» solo muestra productos "
        "de proveedores con «Premium Plus» activo — es un requisito explícito del documento.",
        "form_fields": ["vendedor", "producto", "comision"],
        "querysets": {
            "producto": lambda: Producto.objects.filter(
                publicado=True, empresa__nivel_comercial=Empresa.NivelComercial.PREMIUM_PLUS,
            ),
        },
        "columnas": [
            ("vendedor", "Vendedor"), ("producto", "Producto"),
            ("comision_efectiva", "Comisión %"), ("vinculado_en", "Vinculado"),
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
    ("recurso", "vendedor", "Red Comercial"),
    ("recurso", "requerimiento", "Leads / RFQ"),
    ("recurso", "oportunidad", "Oportunidades"),
    ("recurso", "venta", "Ventas"),
    ("recurso", "comision", "Comisiones"),
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
