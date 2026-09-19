from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.paginator import Paginator
from django.db.models import Q
from django.shortcuts import redirect
from django.urls import reverse_lazy
from django.views.generic import ListView, TemplateView
from django.views.generic.detail import DetailView
from django.views.generic.edit import CreateView, DeleteView, FormMixin, FormView, UpdateView

from catalogo.models import Categoria, Empresa, Producto, Requerimiento, Vendedor
from web.forms import MiEmpresaForm, MiProductoForm, RegistroProveedorForm, RequerimientoForm

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
        return ctx


class QuienesSomos(TemplateView):
    template_name = "web/quienes_somos.html"

    def get_context_data(self, **kw):
        ctx = super().get_context_data(**kw)
        ctx["stats"] = {
            "proveedores": Empresa.objects.filter(
                rol=Empresa.Rol.PROVEEDORA,
                estado_verificacion=Empresa.EstadoVerificacion.VERIFICADA,
            ).count(),
            "productos": Producto.objects.filter(publicado=True).count(),
            "rubros": Categoria.objects.filter(padre__isnull=True).count(),
        }
        return ctx


class ComoFunciona(TemplateView):
    template_name = "web/como_funciona.html"


class Planes(TemplateView):
    template_name = "web/planes.html"


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


class PerfilProveedor(DetailView):
    """Página pública por proveedor (documento de producto, sección 20).
    Muestra lo que hay dato real para: logo, descripción, ubicación, rubros,
    productos publicados y calificación (con el checklist de "información
    revisada", sección 21). «Marcas», «Mercados atendidos» y «Capacidad de
    suministro» son campos del módulo Premium que todavía no existe — no se
    muestran hasta que existan. El contacto de la empresa NO es público: el
    modelo de negocio es de intermediación, el comprador llega al proveedor
    solo a través del formulario de requerimiento."""

    model = Empresa
    slug_url_kwarg = "slug"
    template_name = "web/perfil_proveedor.html"
    context_object_name = "empresa"

    def get_queryset(self):
        return Empresa.objects.filter(rol=Empresa.Rol.PROVEEDORA)

    def get_context_data(self, **kw):
        ctx = super().get_context_data(**kw)
        empresa = self.object
        productos = Producto.objects.filter(empresa=empresa, publicado=True).select_related("categoria")
        ctx["productos"] = productos
        ctx["categorias"] = sorted({p.categoria for p in productos}, key=lambda c: c.nombre)
        ctx["checklist_empresa"] = [
            (empresa._meta.get_field(campo).verbose_name, getattr(empresa, campo))
            for campo in Empresa.CHECKLIST_CALIFICACION[:5]
        ]
        ctx["checklist_producto"] = [
            (empresa._meta.get_field(campo).verbose_name, getattr(empresa, campo))
            for campo in Empresa.CHECKLIST_CALIFICACION[5:]
        ]
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
        codigo = self.request.session.get("ref_vendedor")
        vendedor = Vendedor.objects.filter(
            codigo_referencia=codigo, estado=Vendedor.Estado.ACTIVO,
        ).first() if codigo else None
        if vendedor:
            requerimiento.origen = Requerimiento.Origen.VENDEDOR
            requerimiento.vendedor = vendedor
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


# --- Cuenta de proveedor (autoservicio) -------------------------------------
# Documento de membresías, sección 19 "Panel del proveedor": por ahora solo
# proveedoras (no compradoras) y solo "Mi empresa" / "Mis productos" / "Mi
# membresía" — el resto (Mi Red Comercial, Mis solicitudes, Estadísticas) es
# alcance futuro, ver memoria del proyecto.

class RegistroProveedor(FormView):
    """"Regístra tu empresa" (sección 32). Crea la cuenta y la empresa en el
    mismo paso, siempre en plan Free — no hay pago todavía, así que nadie
    puede autoasignarse un plan pago acá."""

    template_name = "web/cuenta_registro.html"
    form_class = RegistroProveedorForm
    success_url = reverse_lazy("web:cuenta_empresa")

    def dispatch(self, request, *args, **kw):
        if request.user.is_authenticated:
            return redirect("web:cuenta_empresa")
        return super().dispatch(request, *args, **kw)

    def form_valid(self, form):
        user = form.save()
        Empresa.objects.create(
            usuario=user, rol=Empresa.Rol.PROVEEDORA,
            razon_social=form.cleaned_data["razon_social"],
            nombre_comercial=form.cleaned_data["nombre_comercial"],
            identificador_tributario=form.cleaned_data["identificador_tributario"],
            pais=form.cleaned_data["pais"], region=form.cleaned_data["region"],
            ciudad=form.cleaned_data["ciudad"],
        )
        login(self.request, user)
        messages.success(self.request, "¡Listo! Tu empresa quedó registrada en el plan Free.")
        return super().form_valid(form)


class ProveedorMixin(LoginRequiredMixin):
    login_url = "web:cuenta_login"

    def dispatch(self, request, *args, **kw):
        if request.user.is_authenticated and not hasattr(request.user, "empresa"):
            messages.error(request, "Esta cuenta no tiene una empresa asociada a este panel.")
            return redirect("web:home")
        return super().dispatch(request, *args, **kw)


class MiEmpresa(ProveedorMixin, UpdateView):
    """Lo que el proveedor puede tocar de su propio perfil — nunca su estado
    de verificación, calificación o nivel comercial (eso lo decide
    MERCANTE365 desde el panel admin, nunca la propia empresa)."""

    form_class = MiEmpresaForm
    template_name = "web/cuenta_mi_empresa.html"
    success_url = reverse_lazy("web:cuenta_empresa")

    def get_object(self, queryset=None):
        return self.request.user.empresa

    def form_valid(self, form):
        messages.success(self.request, "Datos actualizados.")
        return super().form_valid(form)


class MisProductosLista(ProveedorMixin, ListView):
    template_name = "web/cuenta_productos_lista.html"
    context_object_name = "productos"
    paginate_by = 20

    def get_queryset(self):
        return self.request.user.empresa.productos.all().order_by("-creado")

    def get_context_data(self, **kw):
        ctx = super().get_context_data(**kw)
        empresa = self.request.user.empresa
        ctx["limite"] = empresa.limite_productos()
        ctx["activos"] = empresa.productos_activos_count()
        return ctx


class MisProductosCrear(ProveedorMixin, CreateView):
    form_class = MiProductoForm
    template_name = "web/cuenta_productos_form.html"
    success_url = reverse_lazy("web:cuenta_productos")

    def get_form(self, form_class=None):
        # `empresa` no está en `MiProductoForm` (el proveedor no la elige, es
        # siempre la suya) — hay que fijarla ACÁ, antes de `is_valid()`, no en
        # `form_valid()`: para entonces `Producto.clean()` ya corrió con
        # `empresa_id=None` y el límite de productos del plan nunca se llega
        # a chequear.
        form = super().get_form(form_class)
        form.instance.empresa = self.request.user.empresa
        return form

    def form_valid(self, form):
        messages.success(self.request, "Producto creado.")
        return super().form_valid(form)


class MisProductosEditar(ProveedorMixin, UpdateView):
    form_class = MiProductoForm
    template_name = "web/cuenta_productos_form.html"
    success_url = reverse_lazy("web:cuenta_productos")

    def get_queryset(self):
        return self.request.user.empresa.productos.all()

    def form_valid(self, form):
        messages.success(self.request, "Producto actualizado.")
        return super().form_valid(form)


class MisProductosEliminar(ProveedorMixin, DeleteView):
    template_name = "web/cuenta_productos_confirmar.html"
    success_url = reverse_lazy("web:cuenta_productos")

    def get_queryset(self):
        return self.request.user.empresa.productos.all()


class MiMembresia(ProveedorMixin, TemplateView):
    template_name = "web/cuenta_membresia.html"

    def get_context_data(self, **kw):
        ctx = super().get_context_data(**kw)
        empresa = self.request.user.empresa
        ctx["empresa"] = empresa
        ctx["activos"] = empresa.productos_activos_count()
        ctx["limite"] = empresa.limite_productos()
        return ctx
