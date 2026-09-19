from decimal import Decimal

from django.contrib.auth.models import User
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


class CuentaDeProveedor(TestCase):
    """Autorregistro + panel de autoservicio (documento de membresías,
    secciones 19 y 32) — solo proveedoras por ahora."""

    @classmethod
    def setUpTestData(cls):
        cls.cl = Pais.objects.create(codigo_iso="CL", nombre="Chile")
        cls.reg = Region.objects.create(pais=cls.cl, nombre="RM", slug="rm")
        cls.ciu = Ciudad.objects.create(region=cls.reg, nombre="Santiago", slug="santiago")
        cls.cat = Categoria.objects.create(nombre="Ferretería", slug="ferreteria")

    def _datos_registro(self, username, razon_social, rut):
        return {
            "username": username, "email": f"{username}@ejemplo.cl",
            "password1": "ContraseñaSegura123", "password2": "ContraseñaSegura123",
            "razon_social": razon_social, "nombre_comercial": "", "identificador_tributario": rut,
            "pais": self.cl.pk, "region": self.reg.pk, "ciudad": self.ciu.pk,
        }

    def test_registro_crea_usuario_y_empresa_free_con_slug_solo(self):
        r = self.client.post("/cuenta/registro/", self._datos_registro("prov1", "Uno SpA", "1"))
        self.assertEqual(r.status_code, 302)
        empresa = Empresa.objects.get(razon_social="Uno SpA")
        self.assertEqual(empresa.rol, Empresa.Rol.PROVEEDORA)
        self.assertEqual(empresa.nivel_comercial, Empresa.NivelComercial.FREE)
        self.assertEqual(empresa.slug, "uno-spa")
        self.assertEqual(empresa.usuario.username, "prov1")
        # queda logueado después de registrarse
        self.assertEqual(self.client.get("/cuenta/").status_code, 200)

    def test_cuenta_requiere_login(self):
        r = self.client.get("/cuenta/")
        self.assertEqual(r.status_code, 302)
        self.assertIn("/cuenta/ingresar/", r.url)

    def test_staff_sin_empresa_no_entra_a_cuenta(self):
        User.objects.create_user("staff_solo", password="x", is_staff=True)
        self.client.login(username="staff_solo", password="x")
        r = self.client.get("/cuenta/", follow=True)
        self.assertEqual(r.redirect_chain[-1][0], "/")

    def test_mis_productos_respeta_el_limite_del_plan(self):
        self.client.post("/cuenta/registro/", self._datos_registro("prov2", "Dos SpA", "2"))
        datos = lambda n: {
            "categoria": self.cat.pk, "nombre": f"P{n}", "slug": f"p{n}", "sku": "",
            "descripcion_tecnica": "", "precio_unitario": "1000", "moneda": "CLP",
            "cantidad_minima_pedido": 1, "unidad_empaque": "", "plazo_entrega_dias": 5,
            "stock_disponible": 10, "atributos": "{}", "publicado": "on",
        }
        for n in range(3):
            r = self.client.post("/cuenta/productos/nuevo/", datos(n))
            self.assertEqual(r.status_code, 302, f"producto {n}")

        r = self.client.post("/cuenta/productos/nuevo/", datos(4))
        self.assertEqual(r.status_code, 200)  # rechazado, no redirige
        self.assertContains(r, "el máximo de su plan")
        self.assertEqual(Producto.objects.count(), 3)

    def test_no_puede_editar_ni_borrar_producto_de_otra_empresa(self):
        self.client.post("/cuenta/registro/", self._datos_registro("prov3", "Tres SpA", "3"))
        ajena = Empresa.objects.create(
            rol=Empresa.Rol.PROVEEDORA, razon_social="Ajena SpA", identificador_tributario="9",
            pais=self.cl, region=self.reg, ciudad=self.ciu,
        )
        producto_ajeno = Producto.objects.create(
            empresa=ajena, categoria=self.cat, nombre="No es mío", slug="no-es-mio",
            precio_unitario=Decimal("1"),
        )
        self.assertEqual(self.client.get(f"/cuenta/productos/{producto_ajeno.pk}/").status_code, 404)
        r = self.client.post(f"/cuenta/productos/{producto_ajeno.pk}/eliminar/")
        self.assertEqual(r.status_code, 404)
        self.assertTrue(Producto.objects.filter(pk=producto_ajeno.pk).exists())

    def test_mi_empresa_no_puede_autoverificarse_ni_autocalificarse(self):
        self.client.post("/cuenta/registro/", self._datos_registro("prov4", "Cuatro SpA", "4"))
        empresa = Empresa.objects.get(razon_social="Cuatro SpA")
        self.client.post("/cuenta/", {
            "razon_social": "Cuatro SpA", "nombre_comercial": "", "descripcion": "",
            "pais": self.cl.pk, "region": self.reg.pk, "ciudad": self.ciu.pk,
            "direccion_fisica": "",
            # estos tres no están en el form — no deberían tener ningún efecto:
            "calificado": "on",
            "estado_verificacion": Empresa.EstadoVerificacion.VERIFICADA,
            "nivel_comercial": Empresa.NivelComercial.PREMIUM_PLUS,
        })
        empresa.refresh_from_db()
        self.assertFalse(empresa.calificado)
        self.assertEqual(empresa.estado_verificacion, Empresa.EstadoVerificacion.NO_VERIFICADA)
        self.assertEqual(empresa.nivel_comercial, Empresa.NivelComercial.FREE)
