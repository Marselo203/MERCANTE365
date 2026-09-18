"""
Admin del cliente para MERCANTE365 (el de `django.contrib.admin` queda solo
para desarrollo). CRUD genérico: 4 vistas basadas en clases + un `ModelForm`
autogenerado, configuradas por recurso desde `urls.py`. Sin dependencias.
"""

from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.forms import modelform_factory
from django.urls import reverse
from django.views.generic import (
    CreateView,
    DeleteView,
    ListView,
    TemplateView,
    UpdateView,
)

from catalogo.models import Categoria, Empresa, Producto, Requerimiento


class StaffMixin(LoginRequiredMixin, UserPassesTestMixin):
    """Anónimo → login; autenticado sin `is_staff` → 403."""

    login_url = "panel:login"

    def test_func(self):
        return self.request.user.is_staff


class Dashboard(StaffMixin, TemplateView):
    template_name = "panel/dashboard.html"

    def get_context_data(self, **kw):
        ctx = super().get_context_data(**kw)
        pend = Empresa.EstadoVerificacion.PENDIENTE
        ctx["metricas"] = [
            ("📨", "Requerimientos nuevos", Requerimiento.objects.filter(estado=Requerimiento.Estado.NUEVO).count()),
            ("📦", "Productos publicados", Producto.objects.filter(publicado=True).count()),
            ("⚠️", "Productos sin verificar", Producto.objects.filter(verificado=False).count()),
            ("🏢", "Empresas por verificar", Empresa.objects.filter(estado_verificacion=pend).count()),
            ("🗂️", "Categorías", Categoria.objects.count()),
        ]
        return ctx


# --- CRUD genérico ---------------------------------------------------------

def _celda(valor):
    if isinstance(valor, bool):
        return "Sí" if valor else "No"
    if valor in (None, ""):
        return "—"
    return str(valor)


class _Base(StaffMixin):
    """`recurso` (dict con model, form_fields, columnas, etiquetas y nombres de
    URL) lo inyecta `urls.py` vía `as_view(recurso=...)`. `filtro` (opcional) es
    un dict de igualdad fija (ej. `{"rol": Empresa.Rol.PROVEEDORA}`) que separa
    en su propia sección del menú una porción de un modelo ya existente, sin
    crear un modelo ni una app nueva para eso. `permiso` (opcional): codename
    completo de un permiso de Django (ej. "catalogo.change_producto" o uno
    custom como "catalogo.gestionar_calificacion") que gatea las 4 vistas
    (listar/crear/editar/eliminar) de este recurso — sin él, cualquier staff
    entra igual que antes (los permisos son opt-in por recurso, no rompen
    cuentas de staff existentes que no tengan ningún permiso asignado).
    `request.user.has_perm(...)` siempre da True para superusers."""

    recurso = None

    def test_func(self):
        if not super().test_func():
            return False
        permiso = self.recurso.get("permiso") if self.recurso else None
        return self.request.user.has_perm(permiso) if permiso else True

    def get_success_url(self):
        return reverse(self.recurso["url_list"])

    def get_queryset(self):
        qs = self.recurso["model"].objects.filter(**self.recurso.get("filtro", {}))
        return qs if qs.ordered else qs.order_by("pk")  # paginación determinista

    def get_context_data(self, **kw):
        ctx = super().get_context_data(**kw)
        ctx["recurso"] = self.recurso
        return ctx


class _ConForm(_Base):
    def get_form_class(self):
        """`querysets` (opcional en el recurso): dict `{campo: función sin
        argumentos que devuelve un queryset}` para acotar un `ModelChoiceField`
        más allá de su default (todo el modelo relacionado) — ej. el
        "producto" de una vinculación de vendedor solo puede ser de un
        proveedor Premium Plus (documento de producto, sección 65,
        "IMPORTANTE"). Django ya rechaza en la validación cualquier valor
        fuera de esa queryset, no hace falta repetir la regla a mano."""
        querysets = self.recurso.get("querysets")
        callback = None
        if querysets:
            def callback(db_field, **kw):
                campo = db_field.formfield(**kw)
                if campo is not None and db_field.name in querysets:
                    campo.queryset = querysets[db_field.name]()
                return campo
        return modelform_factory(
            self.recurso["model"], fields=self.recurso["form_fields"], formfield_callback=callback,
        )


class Proximamente(StaffMixin, TemplateView):
    """Sección del Back Office descrita en el documento de producto pero que
    todavía no tiene modelo ni CRUD real (fase posterior a la actual)."""

    template_name = "panel/proximamente.html"
    titulo = None

    def get_context_data(self, **kw):
        ctx = super().get_context_data(**kw)
        ctx["titulo"] = self.titulo
        return ctx


class Lista(_Base, ListView):
    template_name = "panel/list.html"
    paginate_by = 50

    def get_context_data(self, **kw):
        ctx = super().get_context_data(**kw)
        cols = self.recurso["columnas"]
        ctx["encabezados"] = [h for _, h in cols]
        filas = []
        for obj in ctx["object_list"]:
            valores = []
            for attr, _ in cols:
                v = getattr(obj, attr)
                valores.append(_celda(v() if callable(v) else v))
            filas.append({"pk": obj.pk, "valores": valores})
        ctx["filas"] = filas
        return ctx


class Crear(_ConForm, CreateView):
    template_name = "panel/form.html"

    def form_valid(self, form):
        for campo, valor in self.recurso.get("filtro", {}).items():
            setattr(form.instance, campo, valor)
        return super().form_valid(form)


class Editar(_ConForm, UpdateView):
    template_name = "panel/form.html"


class Eliminar(_Base, DeleteView):
    template_name = "panel/confirm_delete.html"
