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
        for slug in ["producto", "empresa", "categoria", "atributo", "imagen", "escala", "contacto"]:
            urls += [f"/panel/{slug}/", f"/panel/{slug}/nuevo/"]
        for url in urls:
            self.assertEqual(self.client.get(url).status_code, 200, url)
