class CapturarReferidoMiddleware:
    """Si la URL trae ?ref=<código>, lo guarda en sesión para poder atribuir
    el requerimiento al vendedor de la Red Comercial que lo trajo, aunque el
    comprador navegue varias páginas antes de enviarlo (documento de
    producto, secciones 66-67: "Tracking URL" / "Atribución del lead")."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        ref = request.GET.get("ref")
        if ref:
            request.session["ref_vendedor"] = ref
        return self.get_response(request)
