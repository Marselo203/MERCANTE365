"""Nav disponible en toda plantilla que extienda panel/base.html, no solo
desde el dashboard. Sigue el orden de `MENU` (el del Back Office descrito en
el documento de producto, mezclando recursos reales y secciones
"Próximamente"). Los recursos que no forman parte de ese menú principal
(subrecursos como atributos, imágenes, escalas o contactos, que se gestionan
sueltos por ahora) se agregan al final para que sigan siendo alcanzables,
salvo los de `OCULTOS`, que no se muestran en ningún lado del menú.

Un recurso con `permiso` solo aparece acá si `request.user` lo tiene (o es
superuser) — evita mostrar links a secciones a las que ese staff no puede
entrar. Las secciones "Próximamente" no tienen permiso propio, son visibles
para cualquier staff (son solo una página fija, no hay nada que proteger)."""

from panel.urls import MENU, OCULTOS, PROXIMAMENTE, RECURSOS

_RECURSOS_POR_SLUG = {r["slug"]: r for r in RECURSOS}
_EN_MENU = {slug for _, slug, *_ in MENU}


def _puede_ver(user, recurso):
    permiso = recurso.get("permiso")
    return user.has_perm(permiso) if permiso else True


def nav(request):
    # El procesador está registrado para TODAS las plantillas, pero este menú
    # solo lo usa panel/base.html. Sin este corte, cada página del sitio
    # público vista por un proveedor logueado cargaba su tabla de permisos
    # (2 queries) para armar un menú que esa plantilla nunca muestra.
    if not getattr(request.user, "is_staff", False):
        return {}

    items = [("panel:dashboard", "Inicio")]
    for entrada in MENU:
        tipo, slug = entrada[0], entrada[1]
        if tipo == "recurso":
            r = _RECURSOS_POR_SLUG[slug]
            if not _puede_ver(request.user, r):
                continue
            etiqueta = entrada[2] if len(entrada) > 2 else r["etiqueta_plural"]
            items.append((f"panel:{r['slug']}_list", etiqueta))
        else:
            items.append((f"panel:proximamente_{slug}", dict(PROXIMAMENTE)[slug]))
    items += [
        (f"panel:{r['slug']}_list", r["etiqueta_plural"])
        for r in RECURSOS
        if r["slug"] not in _EN_MENU
        and r["slug"] not in OCULTOS
        and _puede_ver(request.user, r)
    ]
    return {"panel_nav": items}
