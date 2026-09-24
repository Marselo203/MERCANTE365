"""
Admin del cliente para MERCANTE365 (el de `django.contrib.admin` queda solo
para desarrollo). CRUD genérico: 4 vistas basadas en clases + un `ModelForm`
autogenerado, configuradas por recurso desde `urls.py`. Sin dependencias.
"""

import math
from datetime import date

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.db.models import Count
from django.db.models.functions import TruncMonth
from django.forms import modelform_factory
from django.urls import reverse
from django.utils import timezone
from django.utils.decorators import method_decorator
from django.views.decorators.cache import never_cache
from django.views.generic import (
    CreateView,
    DeleteView,
    ListView,
    TemplateView,
    UpdateView,
)

from catalogo.models import Categoria, Empresa, Producto, Requerimiento

MESES = ["Ene", "Feb", "Mar", "Abr", "May", "Jun", "Jul", "Ago", "Sep", "Oct", "Nov", "Dic"]


@method_decorator(never_cache, name="dispatch")
class StaffMixin(LoginRequiredMixin, UserPassesTestMixin):
    """Anónimo → login; autenticado sin `is_staff` → 403.

    `never_cache` en el `dispatch`: sin esto, el botón "atrás" del navegador
    después de cerrar sesión puede mostrar una página del panel que quedó en
    el caché local, aunque el servidor ya no reconozca la sesión — no es un
    bypass real (una recarga sigue pidiendo login), pero se siente como uno.
    """

    login_url = "panel:login"

    def test_func(self):
        return self.request.user.is_staff


def _ultimos_6_meses():
    hoy = timezone.now().date().replace(day=1)
    meses = []
    y, m = hoy.year, hoy.month
    for _ in range(6):
        meses.append((y, m))
        m -= 1
        if m == 0:
            m, y = 12, y - 1
    return list(reversed(meses))


def _requerimientos_por_mes():
    """Barras de "Result" del dashboard: nada de Lorem Ipsum, cuenta real de
    `Requerimiento.creado` agrupada por mes, con los 6 meses siempre
    presentes (aunque un mes tenga 0)."""
    meses = _ultimos_6_meses()
    desde = date(meses[0][0], meses[0][1], 1)
    conteos = {
        (c["mes"].year, c["mes"].month): c["total"]
        for c in Requerimiento.objects.filter(creado__date__gte=desde)
        .annotate(mes=TruncMonth("creado"))
        .values("mes")
        .annotate(total=Count("id"))
    }
    totales = [conteos.get((y, m), 0) for y, m in meses]
    maximo = max(totales) or 1

    alto_max, base = 100, 130
    ancho_barra, espacio = 36, 18
    barras = []
    for i, ((y, m), total) in enumerate(zip(meses, totales)):
        alto = round(total / maximo * alto_max) if total else 0
        barras.append({
            "x": i * (ancho_barra + espacio),
            "y": base - alto,
            "alto": max(alto, 2) if total else 0,
            "ancho": ancho_barra,
            "etiqueta": MESES[m - 1],
            "total": total,
        })
    ancho_svg = len(barras) * (ancho_barra + espacio) - espacio
    return barras, ancho_svg, base


def _anillo_verificacion():
    """Dona de "productos verificados" (equivalente al 45% del mockup, pero
    con un dato real en vez de uno inventado)."""
    publicados = Producto.objects.filter(publicado=True).count()
    verificados = Producto.objects.filter(
        publicado=True, estado_verificacion=Producto.EstadoVerificacion.VERIFICADO,
    ).count()
    pct = round(verificados / publicados * 100) if publicados else 0
    radio = 42
    circunferencia = 2 * math.pi * radio
    # Enteros a propósito: con decimales el locale es-CL los escribe con coma
    # y el navegador lee stroke-dasharray="187,4 263,9" como cuatro valores
    # (anillo punteado en vez de un arco). Redondear cuesta <0.4% del arco.
    return {
        "pct": pct, "radio": radio, "circunferencia": round(circunferencia),
        "trazo": round(circunferencia * pct / 100),
        "verificados": verificados, "publicados": publicados,
    }


class Dashboard(StaffMixin, TemplateView):
    template_name = "panel/dashboard.html"

    def get_context_data(self, **kw):
        ctx = super().get_context_data(**kw)
        sin_verificar_prod = Producto.EstadoVerificacion.NO_VERIFICADO
        sin_verificar_emp = Empresa.EstadoVerificacion.NO_VERIFICADA
        ctx["metricas"] = [
            ("📨", "Requerimientos nuevos", Requerimiento.objects.filter(estado=Requerimiento.Estado.NUEVO).count()),
            ("📦", "Productos publicados", Producto.objects.filter(publicado=True).count()),
            ("⚠️", "Productos sin verificar", Producto.objects.filter(estado_verificacion=sin_verificar_prod).count()),
            ("🏢", "Empresas por verificar", Empresa.objects.filter(estado_verificacion=sin_verificar_emp).count()),
            ("🗂️", "Categorías", Categoria.objects.count()),
        ]
        ctx["barras"], ctx["barras_ancho"], ctx["barras_base"] = _requerimientos_por_mes()
        ctx["anillo"] = _anillo_verificacion()
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

    def form_valid(self, form):
        response = super().form_valid(form)
        # Genérico a propósito: cualquier modelo puede dejar esta marca en su
        # `save()` (hoy solo `Empresa`, al bajar de nivel comercial) para
        # avisarle al staff que pasó algo más allá de guardar el cambio.
        archivados = getattr(form.instance, "_productos_archivados", 0)
        if archivados:
            messages.warning(
                self.request,
                f"Se desactivaron {archivados} producto{'s' if archivados != 1 else ''} por "
                "superar el límite del nuevo plan (quedaron guardados, no se borraron).",
            )
        return response


class Eliminar(_Base, DeleteView):
    template_name = "panel/confirm_delete.html"
