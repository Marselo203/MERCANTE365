"""Cubre lo único no trivial de los modelos: herencia de atributos y la
validación del JSONB de Producto.  `docker compose exec web python manage.py test`"""

from decimal import Decimal

from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.test import TestCase

from catalogo.models import (
    AtributoDefinicion,
    Categoria,
    Ciudad,
    Empresa,
    ImagenProducto,
    Pais,
    Producto,
    Region,
)


class ValidacionDeAtributos(TestCase):
    @classmethod
    def setUpTestData(cls):
        cl = Pais.objects.create(codigo_iso="CL", nombre="Chile")
        reg = Region.objects.create(pais=cl, nombre="RM", slug="rm")
        ciu = Ciudad.objects.create(region=reg, nombre="Santiago", slug="santiago")
        cls.empresa = Empresa.objects.create(
            rol=Empresa.Rol.PROVEEDORA, razon_social="ACME", identificador_tributario="1",
            slug="acme", pais=cl, region=reg, ciudad=ciu,
        )
        raiz = Categoria.objects.create(nombre="Equipos de red", slug="redes")
        cls.hoja = Categoria.objects.create(padre=raiz, nombre="Switches", slug="switches")
        AtributoDefinicion.objects.create(
            categoria=raiz, clave="puertos", etiqueta="Puertos",
            tipo=AtributoDefinicion.Tipo.NUMERO, obligatorio=True,
        )
        AtributoDefinicion.objects.create(
            categoria=raiz, clave="velocidad", etiqueta="Velocidad",
            tipo=AtributoDefinicion.Tipo.OPCION, opciones=["1 Gbps", "10 Gbps"],
        )

    def producto(self, atributos):
        return Producto(
            empresa=self.empresa, categoria=self.hoja, nombre="P", slug="p",
            precio_unitario=Decimal("1.00"), atributos=atributos,
        )

    def test_la_hoja_hereda_las_definiciones_de_la_ancestra(self):
        self.assertEqual(
            {ad.clave for ad in self.hoja.atributos_heredados()},
            {"puertos", "velocidad"},
        )

    def test_valores_validos_pasan(self):
        self.producto({"puertos": 24, "velocidad": "1 Gbps"}).full_clean()

    def test_rechaza_clave_no_definida(self):
        with self.assertRaises(ValidationError):
            self.producto({"puertos": 1, "color": "rojo"}).full_clean()

    def test_rechaza_tipo_equivocado(self):
        with self.assertRaises(ValidationError):
            self.producto({"puertos": "muchos"}).full_clean()

    def test_rechaza_opcion_fuera_de_lista(self):
        with self.assertRaises(ValidationError):
            self.producto({"puertos": 1, "velocidad": "5 Gbps"}).full_clean()

    def test_exige_los_obligatorios(self):
        with self.assertRaises(ValidationError):
            self.producto({"velocidad": "1 Gbps"}).full_clean()


class DescendientesDeCategoria(TestCase):
    def test_incluye_toda_la_rama(self):
        electronica = Categoria.objects.create(nombre="Electrónica", slug="electronica")
        redes = Categoria.objects.create(padre=electronica, nombre="Equipos de red", slug="redes")
        switches = Categoria.objects.create(padre=redes, nombre="Switches", slug="switches")
        ferreteria = Categoria.objects.create(nombre="Ferretería", slug="ferreteria")

        ids = set(electronica.con_descendientes())
        self.assertEqual(ids, {electronica.pk, redes.pk, switches.pk})
        self.assertNotIn(ferreteria.pk, ids)
        # una hoja se incluye a sí misma, sin hijos
        self.assertEqual(switches.con_descendientes(), [switches.pk])


class ImagenPrincipalUnica(TestCase):
    @classmethod
    def setUpTestData(cls):
        cl = Pais.objects.create(codigo_iso="CL", nombre="Chile")
        reg = Region.objects.create(pais=cl, nombre="RM", slug="rm")
        ciu = Ciudad.objects.create(region=reg, nombre="Santiago", slug="santiago")
        emp = Empresa.objects.create(
            rol=Empresa.Rol.PROVEEDORA, razon_social="ACME", identificador_tributario="1",
            slug="acme", pais=cl, region=reg, ciudad=ciu,
        )
        cat = Categoria.objects.create(nombre="Cables", slug="cables")
        cls.p1 = Producto.objects.create(
            empresa=emp, categoria=cat, nombre="A", slug="a", precio_unitario=Decimal("1"),
        )
        cls.p2 = Producto.objects.create(
            empresa=emp, categoria=cat, nombre="B", slug="b", precio_unitario=Decimal("1"),
        )

    def test_marcar_una_nueva_principal_desplaza_a_la_anterior(self):
        # Antes esto tiraba IntegrityError con el nombre crudo de la
        # constraint — nada legible para el staff del panel. Ahora la nueva
        # principal desplaza a la vieja sola, sin que haya que desmarcarla
        # a mano primero.
        vieja = ImagenProducto.objects.create(producto=self.p1, imagen="x.jpg", es_principal=True)
        nueva = ImagenProducto.objects.create(producto=self.p1, imagen="y.jpg", es_principal=True)
        vieja.refresh_from_db()
        self.assertFalse(vieja.es_principal)
        self.assertTrue(nueva.es_principal)
        self.assertEqual(
            ImagenProducto.objects.filter(producto=self.p1, es_principal=True).count(), 1,
        )

    def test_la_constraint_de_base_sigue_como_red_de_seguridad(self):
        # `validate_constraints` se saltea esta constraint porque `save()` ya
        # la garantiza — pero la constraint de Postgres en sí sigue ahí para
        # cualquier escritura que evite `save()` (ej. `.update()` directo).
        img1 = ImagenProducto.objects.create(producto=self.p1, imagen="x.jpg", es_principal=True)
        img2 = ImagenProducto.objects.create(producto=self.p1, imagen="y.jpg")
        with self.assertRaises(IntegrityError), transaction.atomic():
            ImagenProducto.objects.filter(pk=img2.pk).update(es_principal=True)

    def test_cada_producto_puede_tener_su_principal(self):
        ImagenProducto.objects.create(producto=self.p1, imagen="x.jpg", es_principal=True)
        ImagenProducto.objects.create(producto=self.p2, imagen="y.jpg", es_principal=True)
        # varias NO principales conviven sin problema
        ImagenProducto.objects.create(producto=self.p1, imagen="z.jpg", orden=1)
        ImagenProducto.objects.create(producto=self.p1, imagen="w.jpg", orden=2)


class AdminCargaSinErrores(TestCase):
    """Atrapa lo que `manage.py check` no ve: errores al renderizar
    (autocomplete mal configurado, list_display inválido, métodos que revientan)."""

    @classmethod
    def setUpTestData(cls):
        User.objects.create_superuser("op", "op@ejemplo.cl", "clave-de-prueba")

    def setUp(self):
        self.client.force_login(User.objects.get(username="op"))

    def test_changelists_y_altas_responden_200(self):
        for url in [
            "/django-admin/catalogo/pais/",
            "/django-admin/catalogo/empresa/",
            "/django-admin/catalogo/empresa/add/",
            "/django-admin/catalogo/categoria/",
            "/django-admin/catalogo/categoria/add/",
            "/django-admin/catalogo/producto/",
            "/django-admin/catalogo/producto/add/",
        ]:
            self.assertEqual(self.client.get(url).status_code, 200, url)
