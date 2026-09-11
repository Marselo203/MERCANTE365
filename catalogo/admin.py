from django.contrib import admin
from django.utils.html import format_html

from catalogo.models import (
    AtributoDefinicion,
    Categoria,
    Ciudad,
    ContactoEmpresa,
    Empresa,
    EscalaPrecio,
    ImagenProducto,
    Pais,
    Producto,
    Region,
)


# --- Inlines ---------------------------------------------------------------

class AtributoDefinicionInline(admin.TabularInline):
    model = AtributoDefinicion
    extra = 0


class ContactoEmpresaInline(admin.TabularInline):
    model = ContactoEmpresa
    extra = 0


class EscalaPrecioInline(admin.TabularInline):
    model = EscalaPrecio
    extra = 0


class ImagenProductoInline(admin.TabularInline):
    model = ImagenProducto
    extra = 0
    fields = ["preview", "imagen", "alt", "es_principal", "orden"]
    readonly_fields = ["preview"]

    @admin.display(description="")
    def preview(self, obj):
        if obj.pk and obj.imagen:
            return format_html('<img src="{}" style="height:48px;border-radius:4px">', obj.imagen.url)
        return "—"


# --- Ubicaciones (datos de referencia, sembrados) -----------------------

@admin.register(Pais)
class PaisAdmin(admin.ModelAdmin):
    list_display = ["nombre", "codigo_iso"]
    search_fields = ["nombre", "codigo_iso"]


@admin.register(Region)
class RegionAdmin(admin.ModelAdmin):
    list_display = ["nombre", "pais", "slug"]
    list_filter = ["pais"]
    search_fields = ["nombre", "slug"]
    list_select_related = ["pais"]
    prepopulated_fields = {"slug": ["nombre"]}


@admin.register(Ciudad)
class CiudadAdmin(admin.ModelAdmin):
    list_display = ["nombre", "region", "slug"]
    list_filter = ["region__pais"]
    search_fields = ["nombre", "slug"]
    list_select_related = ["region", "region__pais"]
    autocomplete_fields = ["region"]
    prepopulated_fields = {"slug": ["nombre"]}


# --- Empresas ---------------------------------------------------------------

@admin.register(Empresa)
class EmpresaAdmin(admin.ModelAdmin):
    list_display = ["razon_social", "rol", "estado_verificacion", "pais", "ciudad", "creada"]
    list_editable = ["estado_verificacion"]
    list_filter = ["rol", "estado_verificacion", "pais"]
    search_fields = ["razon_social", "nombre_comercial", "identificador_tributario", "slug"]
    list_select_related = ["pais", "ciudad"]
    autocomplete_fields = ["pais", "region", "ciudad"]
    prepopulated_fields = {"slug": ["razon_social"]}
    inlines = [ContactoEmpresaInline]


# --- Catálogo -------------------------------------------------------------

@admin.register(Categoria)
class CategoriaAdmin(admin.ModelAdmin):
    list_display = ["__str__", "slug", "atributos_propios"]
    list_filter = ["padre"]
    search_fields = ["nombre", "slug"]
    autocomplete_fields = ["padre"]
    prepopulated_fields = {"slug": ["nombre"]}
    inlines = [AtributoDefinicionInline]

    @admin.display(description="atributos propios")
    def atributos_propios(self, obj):
        return obj.atributos.count()


@admin.register(AtributoDefinicion)
class AtributoDefinicionAdmin(admin.ModelAdmin):
    list_display = ["etiqueta", "clave", "categoria", "tipo", "obligatorio", "orden"]
    list_filter = ["tipo", "obligatorio"]
    search_fields = ["clave", "etiqueta"]
    list_select_related = ["categoria"]
    autocomplete_fields = ["categoria"]


@admin.register(Producto)
class ProductoAdmin(admin.ModelAdmin):
    list_display = [
        "nombre", "empresa", "categoria", "precio_unitario", "moneda",
        "stock_disponible", "publicado", "verificado", "destacado",
    ]
    list_editable = ["publicado", "verificado", "destacado"]
    list_filter = ["publicado", "verificado", "destacado", "moneda", "categoria", "empresa"]
    search_fields = ["nombre", "sku", "slug", "empresa__razon_social"]
    list_select_related = ["empresa", "categoria"]
    autocomplete_fields = ["empresa", "categoria"]
    prepopulated_fields = {"slug": ["nombre"]}
    date_hierarchy = "creado"
    readonly_fields = ["creado", "actualizado"]
    inlines = [ImagenProductoInline, EscalaPrecioInline]
