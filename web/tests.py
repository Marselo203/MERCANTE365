from decimal import Decimal

from django.test import TestCase

from catalogo.models import (
    Categoria, Ciudad, ContactoEmpresa, Empresa, Pais, Producto, Region, Requerimiento,
)


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
        ContactoEmpresa.objects.create(
            empresa=emp, nombre="Juan Proveedor", email="contacto-secreto@acme.cl",
            es_principal=True,
        )

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

    def test_el_contacto_de_la_empresa_no_es_publico(self):
        # El modelo de negocio es de intermediación: el comprador llega al
        # proveedor solo a través del formulario de requerimiento, nunca con
        # su email/teléfono directo.
        r = self.client.get(f"/market/{self.publicado_en_hoja.pk}/")
        self.assertNotContains(r, "contacto-secreto@acme.cl")
        r = self.client.get("/proveedores/acme/")
        self.assertNotContains(r, "contacto-secreto@acme.cl")

    def test_perfil_del_proveedor_muestra_solo_productos_publicados(self):
        r = self.client.get("/proveedores/acme/")
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "Switch")
        self.assertNotContains(r, "Tornillo")

    def test_perfil_de_empresa_compradora_da_404(self):
        cl = Pais.objects.get(codigo_iso="CL")
        Empresa.objects.create(
            rol=Empresa.Rol.COMPRADORA, razon_social="Importadora Andes",
            identificador_tributario="2", slug="importadora-andes",
            pais=cl, region=self.publicado_en_hoja.empresa.region,
            ciudad=self.publicado_en_hoja.empresa.ciudad,
        )
        self.assertEqual(self.client.get("/proveedores/importadora-andes/").status_code, 404)

    def test_perfil_muestra_distintivo_calificado_solo_si_esta_marcado(self):
        r = self.client.get("/proveedores/acme/")
        self.assertNotContains(r, "✓ Calificado")
        emp = self.publicado_en_hoja.empresa
        emp.calificado = True
        emp.save()
        r = self.client.get("/proveedores/acme/")
        self.assertContains(r, "✓ Calificado")


class RedComercial(TestCase):
    """Atribución de un requerimiento a un vendedor vía link de referido
    (?ref=código), documento de producto secciones 66-67: el código se
    captura en sesión al entrar por CUALQUIER página y persiste hasta que se
    envía el requerimiento, aunque sea varias páginas después."""

    @classmethod
    def setUpTestData(cls):
        cl = Pais.objects.create(codigo_iso="CL", nombre="Chile")
        reg = Region.objects.create(pais=cl, nombre="RM", slug="rm")
        ciu = Ciudad.objects.create(region=reg, nombre="Santiago", slug="santiago")
        emp = Empresa.objects.create(
            rol=Empresa.Rol.PROVEEDORA, razon_social="ACME", identificador_tributario="1",
            slug="acme", pais=cl, region=reg, ciudad=ciu,
        )
        cat = Categoria.objects.create(nombre="Redes", slug="redes")
        cls.producto = Producto.objects.create(
            empresa=emp, categoria=cat, nombre="Switch", slug="switch",
            precio_unitario=Decimal("100"), publicado=True,
        )
        from catalogo.models import Vendedor

        cls.vendedor = Vendedor.objects.create(nombre="Ana Vende")

    def _enviar_requerimiento(self):
        return self.client.post(f"/market/{self.producto.pk}/", {
            "nombre_contacto": "Juana Pérez", "email_contacto": "juana@ejemplo.bo",
            "telefono_contacto": "", "empresa_compradora": "Importadora Andes",
            "volumen_requerido": "3 pallets", "plazo_esperado": "30 días", "observaciones": "",
        }, follow=True)

    def test_requerimiento_organico_sin_ref(self):
        self._enviar_requerimiento()
        req = Requerimiento.objects.get()
        self.assertEqual(req.origen, Requerimiento.Origen.ORGANICO)
        self.assertIsNone(req.vendedor)

    def test_ref_capturado_en_home_persiste_hasta_el_requerimiento(self):
        self.client.get("/", {"ref": self.vendedor.codigo_referencia})
        self._enviar_requerimiento()
        req = Requerimiento.objects.get()
        self.assertEqual(req.origen, Requerimiento.Origen.VENDEDOR)
        self.assertEqual(req.vendedor, self.vendedor)

    def test_ref_de_vendedor_inactivo_no_atribuye(self):
        self.vendedor.estado = self.vendedor.Estado.INACTIVO
        self.vendedor.save()
        self.client.get(f"/market/{self.producto.pk}/", {"ref": self.vendedor.codigo_referencia})
        self._enviar_requerimiento()
        req = Requerimiento.objects.get()
        self.assertEqual(req.origen, Requerimiento.Origen.ORGANICO)
        self.assertIsNone(req.vendedor)

    def test_ref_invalido_no_rompe_nada(self):
        self.client.get(f"/market/{self.producto.pk}/", {"ref": "no-existe"})
        r = self._enviar_requerimiento()
        self.assertEqual(r.status_code, 200)
        req = Requerimiento.objects.get()
        self.assertEqual(req.origen, Requerimiento.Origen.ORGANICO)
