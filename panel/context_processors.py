"""Nav disponible en toda plantilla que extienda panel/base.html, no solo
desde el dashboard. Se arma desde `RECURSOS` de urls.py: agregar un recurso ahí
alcanza para que aparezca en el menú también."""

from panel.urls import RECURSOS


def nav(request):
    items = [("panel:dashboard", "Inicio")]
    items += [(f"panel:{r['slug']}_list", r["etiqueta_plural"]) for r in RECURSOS]
    return {"panel_nav": items}
