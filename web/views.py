from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Q
from django.views.generic import TemplateView
from django.views.generic.detail import DetailView
from django.views.generic.edit import FormMixin

from catalogo.models import Categoria, Empresa, Producto
from web.forms import RequerimientoForm

ORDEN = {
    "precio_asc": "precio_unitario",
    "precio_desc": "-precio_unitario",
}


class Home(TemplateView):
    template_name = "web/home.html"

    def get_context_data(self, **kw):
        ctx = super().get_context_data(**kw)
        ctx["destacados"] = (
            Producto.objects.filter(publicado=True, destacado=True)
            .select_related("empresa", "categoria")[:8]
        )
        ctx["stats"] = {
            "proveedores": Empresa.objects.filter(
                rol=Empresa.Rol.PROVEEDORA,
                estado_verificacion=Empresa.EstadoVerificacion.APROBADA,
            ).count(),
            "productos": Producto.objects.filter(publicado=True).count(),
            "rubros": Categoria.objects.filter(padre__isnull=True).count(),
        }
        return ctx


class Market(TemplateView):
    """Catálogo público con búsqueda, filtro por rubro (con subcategorías) y
    orden. Referencia de layout: Marketplace.dc.html — sin JS, todo por
    querystring para que funcione igual en cualquier dispositivo."""

    template_name = "web/market.html"

    def get_context_data(self, **kw):
        ctx = super().get_context_data(**kw)
        get = self.request.GET

        qs = Producto.objects.filter(publicado=True).select_related("empresa", "categoria")

        q = get.get("q", "").strip()
        if q:
            qs = qs.filter(
                Q(nombre__icontains=q)
                | Q(sku__icontains=q)
                | Q(empresa__razon_social__icontains=q)
                | Q(empresa__nombre_comercial__icontains=q)
                | Q(categoria__nombre__icontains=q)
            )

        categoria_activa = get.get("categoria", "").strip()
        categoria_activa_obj = None
        if categoria_activa:
            categoria_activa_obj = Categoria.objects.filter(
                slug=categoria_activa, padre__isnull=True
            ).first()
            if categoria_activa_obj:
                qs = qs.filter(categoria_id__in=categoria_activa_obj.con_descendientes())

        orden = get.get("orden", "")
        qs = qs.order_by(ORDEN.get(orden, "-creado"))

        paginador = Paginator(qs, 12)
        page_obj = paginador.get_page(get.get("page"))

        params = get.copy()
        params.pop("page", None)
        qs_sin_page = params.urlencode()

        categorias = [
            {
                "nombre": cat.nombre,
                "slug": cat.slug,
                "num_productos": Producto.objects.filter(
                    categoria_id__in=cat.con_descendientes(), publicado=True
                ).count(),
            }
            for cat in Categoria.objects.filter(padre__isnull=True).order_by("nombre")
        ]

        ctx.update({
            "q": q,
            "orden": orden,
            "categoria_activa": categoria_activa,
            "categoria_activa_obj": categoria_activa_obj,
            "categorias": categorias,
            "page_obj": page_obj,
            "total": paginador.count,
            "querystring_sin_page": f"{qs_sin_page}&" if qs_sin_page else "",
        })
        return ctx


class ProductoDetalle(FormMixin, DetailView):
    """Ficha de producto + el "enviar requerimiento" del mockup, en la misma
    página: patrón documentado de Django (FormMixin + DetailView) en vez de
    una vista aparte para el POST."""

    model = Producto
    form_class = RequerimientoForm
    template_name = "web/producto_detalle.html"
    context_object_name = "producto"

    def get_queryset(self):
        return Producto.objects.filter(publicado=True).select_related("empresa", "categoria")

    def get_success_url(self):
        return self.request.path

    def get(self, request, *args, **kw):
        self.object = self.get_object()
        return super().get(request, *args, **kw)

    def post(self, request, *args, **kw):
        self.object = self.get_object()
        form = self.get_form()
        if form.is_valid():
            return self.form_valid(form)
        return self.form_invalid(form)

    def form_valid(self, form):
        requerimiento = form.save(commit=False)
        requerimiento.producto = self.object
        requerimiento.save()
        messages.success(
            self.request,
            "¡Listo! Tu requerimiento fue enviado. Te contactamos en 24 a 48 horas hábiles.",
        )
        return super().form_valid(form)

    def get_context_data(self, **kw):
        ctx = super().get_context_data(**kw)
        producto = self.object
        definiciones = {d.clave: d for d in producto.categoria.atributos_heredados()}
        ctx["atributos_mostrar"] = [
            (definiciones[clave].etiqueta, valor, definiciones[clave].unidad)
            for clave, valor in producto.atributos.items()
            if clave in definiciones
        ]
        ctx["contacto"] = producto.empresa.contactos.filter(es_principal=True).first()
        return ctx
