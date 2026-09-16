from django.contrib.auth.models import User
from django.test import TestCase


class AccesoPanel(TestCase):
    @classmethod
    def setUpTestData(cls):
        User.objects.create_user("staff", password="x", is_staff=True)
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
        ]:
            urls += [f"/panel/{slug}/", f"/panel/{slug}/nuevo/"]
        urls.append("/panel/calificacion/")  # sin "nuevo/": es sin_alta
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
        for slug in ["catalogos", "premium", "red_comercial", "configuracion"]:
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
