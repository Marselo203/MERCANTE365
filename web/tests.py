from decimal import Decimal

from django.test import TestCase

from catalogo.models import Categoria, Ciudad, Empresa, Pais, Producto, Region, Requerimiento


class Landing(TestCase):
    def test_home_responde_200_sin_destacados(self):
        self.assertEqual(self.client.get("/").status_code, 200)


class MarketYFicha(TestCase):
    @classmethod
    def setUpTestData(cls):
        cl = Pais.objects.create(codigo_iso="CL", nombre="Chile")
        reg = Region.objects.create(pais=cl, nombre="RM", slug="rm")
        ciu = Ciudad.objects.create(region=reg, nombre="Santiago", slug="santiago")
        emp = Empresa.objects.create(
            rol=Empresa.Rol.PROVEEDORA, razon_social="ACME", identificador_tributario="1",
            slug="acme", pais=cl, region=reg, ciudad=ciu,
        )
        electronica = Categoria.objects.create(nombre="Electrónica", slug="electronica")
        redes = Categoria.objects.create(padre=electronica, nombre="Redes", slug="redes")
        ferreteria = Categoria.objects.create(nombre="Ferretería", slug="ferreteria")

        cls.publicado_en_hoja = Producto.objects.create(
            empresa=emp, categoria=redes, nombre="Switch", slug="switch",
            precio_unitario=Decimal("100"), publicado=True,
        )
        cls.no_publicado = Producto.objects.create(
            empresa=emp, categoria=ferreteria, nombre="Tornillo", slug="tornillo",
            precio_unitario=Decimal("1"), publicado=False,
        )
        cls.electronica, cls.ferreteria = electronica, ferreteria

    def test_market_responde_200(self):
        self.assertEqual(self.client.get("/market/").status_code, 200)

    def test_market_solo_lista_publicados(self):
        r = self.client.get("/market/")
        self.assertContains(r, "Switch")
        self.assertNotContains(r, "Tornillo")

    def test_filtro_por_rubro_raiz_incluye_subcategorias(self):
        # el producto vive en "Redes" (hija de "Electrónica"), filtrar por la
        # raíz debe encontrarlo igual (con_descendientes)
        r = self.client.get("/market/", {"categoria": "electronica"})
        self.assertContains(r, "Switch")
        r = self.client.get("/market/", {"categoria": "ferreteria"})
        self.assertNotContains(r, "Switch")

    def test_buscador_por_nombre(self):
        r = self.client.get("/market/", {"q": "switch"})
        self.assertContains(r, "Switch")
        r = self.client.get("/market/", {"q": "inexistente"})
        self.assertNotContains(r, "Switch")

    def test_ficha_de_producto_publicado(self):
        r = self.client.get(f"/market/{self.publicado_en_hoja.pk}/")
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "Switch")

    def test_ficha_de_producto_no_publicado_da_404(self):
        r = self.client.get(f"/market/{self.no_publicado.pk}/")
        self.assertEqual(r.status_code, 404)

    def test_ficha_de_producto_inexistente_da_404(self):
        self.assertEqual(self.client.get("/market/999999/").status_code, 404)

    def test_formulario_de_requerimiento_aparece_en_la_ficha(self):
        r = self.client.get(f"/market/{self.publicado_en_hoja.pk}/")
        self.assertContains(r, "Enviar requerimiento")
        self.assertContains(r, 'name="nombre_contacto"')

    def test_enviar_requerimiento_valido_lo_guarda_y_confirma(self):
        r = self.client.post(f"/market/{self.publicado_en_hoja.pk}/", {
            "nombre_contacto": "Juana Pérez",
            "email_contacto": "juana@ejemplo.bo",
            "telefono_contacto": "",
            "empresa_compradora": "Importadora Andes",
            "volumen_requerido": "3 pallets / mes",
            "plazo_esperado": "30 días",
            "observaciones": "",
        }, follow=True)
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "Tu requerimiento fue enviado")
        req = Requerimiento.objects.get()
        self.assertEqual(req.producto, self.publicado_en_hoja)
        self.assertEqual(req.email_contacto, "juana@ejemplo.bo")
        self.assertEqual(req.estado, Requerimiento.Estado.NUEVO)

    def test_enviar_requerimiento_invalido_no_guarda_nada(self):
        r = self.client.post(f"/market/{self.publicado_en_hoja.pk}/", {
            "nombre_contacto": "",  # obligatorio, vacío
            "email_contacto": "no-es-un-email",
        })
        self.assertEqual(r.status_code, 200)
        self.assertEqual(Requerimiento.objects.count(), 0)
        self.assertContains(r, "errorlist")
