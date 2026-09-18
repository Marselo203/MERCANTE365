from django.contrib.auth.models import Group, User
from django.test import TestCase


class AccesoPanel(TestCase):
    """"staff" tiene acceso completo (grupo "Staff completo", el mismo que la
    migración 0009 le da a todo staff preexistente) — representa al admin de
    siempre. Los tests de permisos finos usan sus propios usuarios acotados."""

    @classmethod
    def setUpTestData(cls):
        staff = User.objects.create_user("staff", password="x", is_staff=True)
        staff.groups.add(Group.objects.get(name="Staff completo"))
        User.objects.create_user("cliente", password="x", is_staff=False)

    def test_anonimo_redirige_a_ingresar(self):
        r = self.client.get("/panel/")
        self.assertEqual(r.status_code, 302)
        self.assertIn("/panel/ingresar/", r.url)

    def test_autenticado_sin_staff_recibe_403(self):
        self.client.login(username="cliente", password="x")
        self.assertEqual(self.client.get("/panel/").status_code, 403)

    def test_staff_recorre_las_vistas(self):
        self.client.login(username="staff", password="x")
        urls = ["/panel/"]
        for slug in [
            "producto", "empresa", "proveedor", "comprador", "categoria",
            "atributo", "imagen", "escala", "contacto", "requerimiento",
            "vendedor", "vinculacion", "oportunidad", "venta",
        ]:
            urls += [f"/panel/{slug}/", f"/panel/{slug}/nuevo/"]
        urls += ["/panel/calificacion/", "/panel/comision/"]  # sin "nuevo/": son sin_alta
        for url in urls:
            self.assertEqual(self.client.get(url).status_code, 200, url)

    def test_calificacion_no_tiene_alta_ni_baja(self):
        self.client.login(username="staff", password="x")
        self.assertEqual(self.client.get("/panel/calificacion/nuevo/").status_code, 404)
        self.assertEqual(self.client.get("/panel/calificacion/1/eliminar/").status_code, 404)

    def test_proveedor_solo_lista_empresas_con_ese_rol(self):
        from catalogo.models import Ciudad, Empresa, Pais, Region

        self.client.login(username="staff", password="x")
        cl = Pais.objects.create(codigo_iso="CL", nombre="Chile")
        reg = Region.objects.create(pais=cl, nombre="RM", slug="rm")
        ciu = Ciudad.objects.create(region=reg, nombre="Santiago", slug="santiago")
        proveedora = Empresa.objects.create(
            rol=Empresa.Rol.PROVEEDORA, razon_social="Prov SA", identificador_tributario="1",
            slug="prov-sa", pais=cl, region=reg, ciudad=ciu,
        )
        compradora = Empresa.objects.create(
            rol=Empresa.Rol.COMPRADORA, razon_social="Compr SA", identificador_tributario="2",
            slug="compr-sa", pais=cl, region=reg, ciudad=ciu,
        )
        r = self.client.get("/panel/proveedor/")
        vistos = {fila["pk"] for fila in r.context["filas"]}
        self.assertIn(proveedora.pk, vistos)
        self.assertNotIn(compradora.pk, vistos)

    def test_staff_recorre_las_secciones_proximamente(self):
        self.client.login(username="staff", password="x")
        for slug in ["catalogos", "premium", "configuracion"]:
            self.assertEqual(self.client.get(f"/panel/proximamente/{slug}/").status_code, 200, slug)

    def test_checklist_de_calificacion_actualiza_progreso_y_calificado(self):
        from catalogo.models import Ciudad, Empresa, Pais, Region

        self.client.login(username="staff", password="x")
        cl = Pais.objects.create(codigo_iso="CL", nombre="Chile")
        reg = Region.objects.create(pais=cl, nombre="RM", slug="rm")
        ciu = Ciudad.objects.create(region=reg, nombre="Santiago", slug="santiago")
        proveedora = Empresa.objects.create(
            rol=Empresa.Rol.PROVEEDORA, razon_social="Prov SA", identificador_tributario="1",
            slug="prov-sa", pais=cl, region=reg, ciudad=ciu,
        )
        self.assertEqual(proveedora.progreso_checklist(), "0/10")

        r = self.client.post(f"/panel/calificacion/{proveedora.pk}/", {
            "chk_info_empresarial": "on", "chk_contacto_revisado": "on",
            "documentacion_estado": "revisada", "calificado": "on",
        })
        self.assertEqual(r.status_code, 302)
        proveedora.refresh_from_db()
        self.assertEqual(proveedora.progreso_checklist(), "2/10")
        self.assertTrue(proveedora.calificado)

        # El formulario de "proveedor" no expone "calificado": el proveedor
        # no puede autodeclararse calificado editando su propia ficha.
        form = self.client.get(f"/panel/proveedor/{proveedora.pk}/").context["form"]
        self.assertNotIn("calificado", form.fields)

    def test_vendedor_genera_codigo_de_referencia_solo(self):
        from catalogo.models import Vendedor

        v = Vendedor.objects.create(nombre="Carlos Pérez")
        self.assertEqual(v.codigo_referencia, "V-CARLOS-PEREZ")

        v2 = Vendedor.objects.create(nombre="Carlos Pérez")
        self.assertNotEqual(v.codigo_referencia, v2.codigo_referencia)

    def test_vincular_vendedor_solo_permite_productos_premium_plus(self):
        from decimal import Decimal

        from catalogo.models import Categoria, Ciudad, Empresa, Pais, Producto, Region, Vendedor

        self.client.login(username="staff", password="x")
        cl = Pais.objects.create(codigo_iso="CL", nombre="Chile")
        reg = Region.objects.create(pais=cl, nombre="RM", slug="rm")
        ciu = Ciudad.objects.create(region=reg, nombre="Santiago", slug="santiago")
        cat = Categoria.objects.create(nombre="Ferretería", slug="ferreteria")

        free = Empresa.objects.create(
            rol=Empresa.Rol.PROVEEDORA, razon_social="Free SA", identificador_tributario="1",
            slug="free-sa", pais=cl, region=reg, ciudad=ciu,
        )
        plus = Empresa.objects.create(
            rol=Empresa.Rol.PROVEEDORA, razon_social="Plus SA", identificador_tributario="2",
            slug="plus-sa", pais=cl, region=reg, ciudad=ciu,
            nivel_comercial=Empresa.NivelComercial.PREMIUM_PLUS,
        )
        prod_free = Producto.objects.create(
            empresa=free, categoria=cat, nombre="Tornillos", slug="tornillos",
            precio_unitario=Decimal("1"), publicado=True,
        )
        prod_plus = Producto.objects.create(
            empresa=plus, categoria=cat, nombre="Clavos", slug="clavos",
            precio_unitario=Decimal("1"), publicado=True,
        )
        vendedor = Vendedor.objects.create(nombre="Ana Vende")

        form = self.client.get("/panel/vinculacion/nuevo/").context["form"]
        productos_disponibles = set(form.fields["producto"].queryset)
        self.assertIn(prod_plus, productos_disponibles)
        self.assertNotIn(prod_free, productos_disponibles)

        r = self.client.post("/panel/vinculacion/nuevo/", {
            "vendedor": vendedor.pk, "producto": prod_free.pk, "comision": "",
        })
        self.assertEqual(r.status_code, 200)  # form inválido, no redirige
        self.assertContains(r, "errorlist")

        r = self.client.post("/panel/vinculacion/nuevo/", {
            "vendedor": vendedor.pk, "producto": prod_plus.pk, "comision": "5.00",
        })
        self.assertEqual(r.status_code, 302)


class PermisosFinos(TestCase):
    """Un staff con un permiso acotado (ej. solo Calificación) entra a esa
    sección pero no a las demás, y su nav ni siquiera las lista."""

    @classmethod
    def setUpTestData(cls):
        from django.contrib.auth.models import Permission

        cls.solo_calificacion = User.objects.create_user(
            "calificador", password="x", is_staff=True,
        )
        cls.solo_calificacion.user_permissions.add(
            Permission.objects.get(codename="gestionar_calificacion")
        )

    def test_entra_a_su_recurso_pero_no_a_otros(self):
        self.client.login(username="calificador", password="x")
        self.assertEqual(self.client.get("/panel/calificacion/").status_code, 200)
        self.assertEqual(self.client.get("/panel/producto/").status_code, 403)
        self.assertEqual(self.client.get("/panel/vendedor/").status_code, 403)

    def test_su_nav_solo_lista_lo_que_puede_ver(self):
        self.client.login(username="calificador", password="x")
        panel_nav = dict(self.client.get("/panel/").context["panel_nav"])
        self.assertIn("panel:calificacion_list", panel_nav)
        self.assertNotIn("panel:producto_list", panel_nav)
        self.assertNotIn("panel:vendedor_list", panel_nav)


class OportunidadesVentasComisiones(TestCase):
    """Pipeline completo: requerimiento → oportunidad → venta → comisión,
    con y sin vendedor atribuido (documento de producto, secciones 70-73)."""

    @classmethod
    def setUpTestData(cls):
        from decimal import Decimal

        from catalogo.models import (
            Categoria, Ciudad, Empresa, Pais, Producto, Region, Requerimiento, Vendedor,
        )

        staff = User.objects.create_user("vendedor_ops", password="x", is_staff=True)
        staff.groups.add(Group.objects.get(name="Staff completo"))
        cls.staff_password = "x"

        cl = Pais.objects.create(codigo_iso="CL", nombre="Chile")
        reg = Region.objects.create(pais=cl, nombre="RM", slug="rm")
        ciu = Ciudad.objects.create(region=reg, nombre="Santiago", slug="santiago")
        cat = Categoria.objects.create(nombre="Redes", slug="redes")
        emp = Empresa.objects.create(
            rol=Empresa.Rol.PROVEEDORA, razon_social="ACME", identificador_tributario="1",
            slug="acme", pais=cl, region=reg, ciudad=ciu,
        )
        cls.producto = Producto.objects.create(
            empresa=emp, categoria=cat, nombre="Switch", slug="switch",
            precio_unitario=Decimal("100"), publicado=True,
        )
        cls.vendedor = Vendedor.objects.create(nombre="Ana Vende", comision=Decimal("10.00"))

        cls.req_organico = Requerimiento.objects.create(
            producto=cls.producto, nombre_contacto="Juan", email_contacto="juan@x.cl",
        )
        cls.req_con_vendedor = Requerimiento.objects.create(
            producto=cls.producto, nombre_contacto="Ana", email_contacto="ana@x.cl",
            origen=Requerimiento.Origen.VENDEDOR, vendedor=cls.vendedor,
        )

    def setUp(self):
        self.client.login(username="vendedor_ops", password=self.staff_password)

    def test_venta_solo_permite_oportunidades_ganadas(self):
        from catalogo.models import Oportunidad

        op = Oportunidad.objects.create(requerimiento=self.req_organico)
        form = self.client.get("/panel/venta/nuevo/").context["form"]
        self.assertNotIn(op, set(form.fields["oportunidad"].queryset))

        op.estado = Oportunidad.Estado.GANADA
        op.save()
        form = self.client.get("/panel/venta/nuevo/").context["form"]
        self.assertIn(op, set(form.fields["oportunidad"].queryset))

    def test_venta_sin_vendedor_no_genera_comision(self):
        from catalogo.models import Comision, Oportunidad

        op = Oportunidad.objects.create(
            requerimiento=self.req_organico, estado=Oportunidad.Estado.GANADA,
        )
        r = self.client.post("/panel/venta/nuevo/", {
            "oportunidad": op.pk, "monto": "1000000", "comprobante_externo": "",
            "fecha": "2026-09-18", "observaciones": "",
        })
        self.assertEqual(r.status_code, 302)
        self.assertEqual(Comision.objects.count(), 0)

    def test_venta_con_vendedor_calcula_la_comision_sola(self):
        from decimal import Decimal

        from catalogo.models import Comision, Oportunidad

        op = Oportunidad.objects.create(
            requerimiento=self.req_con_vendedor, estado=Oportunidad.Estado.GANADA,
        )
        r = self.client.post("/panel/venta/nuevo/", {
            "oportunidad": op.pk, "monto": "1000000", "comprobante_externo": "F-001",
            "fecha": "2026-09-18", "observaciones": "",
        })
        self.assertEqual(r.status_code, 302)
        comision = Comision.objects.get()
        self.assertEqual(comision.porcentaje, Decimal("10.00"))
        self.assertEqual(comision.monto, Decimal("100000.00"))
        self.assertEqual(comision.vendedor(), self.vendedor)
        self.assertEqual(comision.producto(), self.producto)
        self.assertEqual(comision.estado, Comision.Estado.PENDIENTE)

    def test_comision_no_tiene_alta_ni_baja(self):
        self.assertEqual(self.client.get("/panel/comision/nuevo/").status_code, 404)
        self.assertEqual(self.client.get("/panel/comision/1/eliminar/").status_code, 404)


class GestionDeImagenes(TestCase):
    """El módulo de fotos de producto funcionando de punta a punta desde el
    panel: subir una imagen y marcar una nueva como principal no puede
    tirarle al staff un error de nombre de constraint de base de datos."""

    @classmethod
    def setUpTestData(cls):
        from decimal import Decimal

        from catalogo.models import Categoria, Ciudad, Empresa, Pais, Producto, Region

        staff = User.objects.create_user("fotografo", password="x", is_staff=True)
        staff.groups.add(Group.objects.get(name="Staff completo"))

        cl = Pais.objects.create(codigo_iso="CL", nombre="Chile")
        reg = Region.objects.create(pais=cl, nombre="RM", slug="rm")
        ciu = Ciudad.objects.create(region=reg, nombre="Santiago", slug="santiago")
        cat = Categoria.objects.create(nombre="Redes", slug="redes")
        emp = Empresa.objects.create(
            rol=Empresa.Rol.PROVEEDORA, razon_social="ACME", identificador_tributario="1",
            slug="acme", pais=cl, region=reg, ciudad=ciu,
        )
        cls.producto = Producto.objects.create(
            empresa=emp, categoria=cat, nombre="Switch", slug="switch",
            precio_unitario=Decimal("100"),
        )

    def setUp(self):
        self.client.login(username="fotografo", password="x")

    @staticmethod
    def _png():
        import struct
        import zlib

        from django.core.files.uploadedfile import SimpleUploadedFile

        def chunk(tag, data):
            return struct.pack(">I", len(data)) + tag + data + struct.pack(">I", zlib.crc32(tag + data))

        raw = zlib.compress(b"".join(b"\x00\xff\x00\x00" for _ in range(2)))
        contenido = (
            b"\x89PNG\r\n\x1a\n"
            + chunk(b"IHDR", struct.pack(">IIBBBBB", 2, 2, 8, 2, 0, 0, 0))
            + chunk(b"IDAT", raw)
            + chunk(b"IEND", b"")
        )
        return SimpleUploadedFile("foto.png", contenido, content_type="image/png")

    def test_subir_imagen_principal_y_reemplazarla_no_rompe(self):
        from catalogo.models import ImagenProducto

        r1 = self.client.post("/panel/imagen/nuevo/", {
            "producto": self.producto.pk, "alt": "Foto 1", "es_principal": "on",
            "orden": 1, "imagen": self._png(),
        })
        self.assertEqual(r1.status_code, 302, r1.context["form"].errors if r1.status_code == 200 else "")

        r2 = self.client.post("/panel/imagen/nuevo/", {
            "producto": self.producto.pk, "alt": "Foto 2", "es_principal": "on",
            "orden": 2, "imagen": self._png(),
        })
        self.assertEqual(r2.status_code, 302, r2.context["form"].errors if r2.status_code == 200 else "")

        imagenes = list(ImagenProducto.objects.filter(producto=self.producto).order_by("orden"))
        self.assertEqual(len(imagenes), 2)
        self.assertFalse(imagenes[0].es_principal)
        self.assertTrue(imagenes[1].es_principal)
        self.assertEqual(self.producto.imagen_principal, imagenes[1])
