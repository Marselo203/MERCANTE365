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
            ("Requerimientos nuevos", Requerimiento.objects.filter(estado=Requerimiento.Estado.NUEVO).count()),
            ("Productos publicados", Producto.objects.filter(publicado=True).count()),
            ("Productos sin verificar", Producto.objects.filter(verificado=False).count()),
            ("Empresas por verificar", Empresa.objects.filter(estado_verificacion=pend).count()),
            ("Categorías", Categoria.objects.count()),
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
    crear un modelo ni una app nueva para eso."""

    recurso = None

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
        return modelform_factory(self.recurso["model"], fields=self.recurso["form_fields"])


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
