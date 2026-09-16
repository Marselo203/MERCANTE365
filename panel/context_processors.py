"""Nav disponible en toda plantilla que extienda panel/base.html, no solo
desde el dashboard. Sigue el orden de `MENU` (el del Back Office descrito en
el documento de producto, mezclando recursos reales y secciones
"Próximamente"). Los recursos que no forman parte de ese menú principal
(subrecursos como atributos, imágenes, escalas o contactos, que se gestionan
sueltos por ahora) se agregan al final para que sigan siendo alcanzables."""

from panel.urls import MENU, PROXIMAMENTE, RECURSOS

_RECURSOS_POR_SLUG = {r["slug"]: r for r in RECURSOS}
_EN_MENU = {slug for _, slug, *_ in MENU}


def nav(request):
    items = [("panel:dashboard", "Inicio")]
    for entrada in MENU:
        tipo, slug = entrada[0], entrada[1]
        if tipo == "recurso":
            r = _RECURSOS_POR_SLUG[slug]
            etiqueta = entrada[2] if len(entrada) > 2 else r["etiqueta_plural"]
            items.append((f"panel:{r['slug']}_list", etiqueta))
        else:
            items.append((f"panel:proximamente_{slug}", dict(PROXIMAMENTE)[slug]))
    items += [
        (f"panel:{r['slug']}_list", r["etiqueta_plural"])
        for r in RECURSOS
        if r["slug"] not in _EN_MENU
    ]
    return {"panel_nav": items}
