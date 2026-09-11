"""
catalogo/management/commands/seed_demo.py

Datos ficticios para trabajar en el admin sin cargar todo a mano. Cubre el caso
difícil a propósito: una categoría de tres niveles con atributos técnicos, y un
producto simple sin atributos, para que veas cómo se comportan los dos extremos.

    python manage.py seed_demo
    python manage.py seed_demo --limpiar   # borra lo anterior antes de recrear

NO lo corras en producción. Refuerza con DJANGO_DEBUG.
"""

from decimal import Decimal

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from catalogo.models import (
    AtributoDefinicion,
    Categoria,
    Ciudad,
    ContactoEmpresa,
    Empresa,
    EscalaPrecio,
    Pais,
    Producto,
)


class Command(BaseCommand):
    help = "Carga empresas, categorías y productos de demostración."

    def add_arguments(self, parser):
        parser.add_argument("--limpiar", action="store_true", help="Borra los datos demo previos.")

    @transaction.atomic
    def handle(self, *args, **opciones):
        if not settings.DEBUG:
            raise CommandError("seed_demo solo corre con DJANGO_DEBUG=1.")

        if not Pais.objects.exists():
            raise CommandError("Corre primero: python manage.py seed_ubicaciones")

        if opciones["limpiar"]:
            Producto.objects.filter(empresa__slug__startswith="demo-").delete()
            Empresa.objects.filter(slug__startswith="demo-").delete()
            Categoria.objects.all().delete()
            self.stdout.write(self.style.WARNING("Datos demo anteriores eliminados."))

        # --- Empresas -------------------------------------------------------
        santiago = Ciudad.objects.get(slug="santiago")
        la_paz = Ciudad.objects.get(slug="la-paz", region__pais="BO")

        proveedora, _ = Empresa.objects.get_or_create(
            slug="demo-andes-suministros",
            defaults={
                "rol": Empresa.Rol.PROVEEDORA,
                "razon_social": "Andes Suministros Industriales SpA",
                "nombre_comercial": "Andes Suministros",
                "identificador_tributario": "761234567",
                "pais_id": "CL",
                "region": santiago.region,
                "ciudad": santiago,
                "direccion_fisica": "Av. Vicuña Mackenna 1234, Santiago",
                "descripcion": "Distribuidor de equipamiento industrial y de redes.",
                "estado_verificacion": Empresa.EstadoVerificacion.APROBADA,
            },
        )
        ContactoEmpresa.objects.get_or_create(
            empresa=proveedora,
            email="ventas@ejemplo-andes.cl",
            defaults={"nombre": "Carolina Soto", "cargo": "Jefa comercial",
                      "telefono": "+56 9 1234 5678", "es_principal": True},
        )

        compradora, _ = Empresa.objects.get_or_create(
            slug="demo-importadora-illimani",
            defaults={
                "rol": Empresa.Rol.COMPRADORA,
                "razon_social": "Importadora Illimani SRL",
                "identificador_tributario": "1023456789",
                "pais_id": "BO",
                "region": la_paz.region,
                "ciudad": la_paz,
                "direccion_fisica": "Av. Montes 500, La Paz",
                "estado_verificacion": Empresa.EstadoVerificacion.PENDIENTE,
            },
        )

        # --- Categorías anidadas (3 niveles) --------------------------------
        electronica, _ = Categoria.objects.get_or_create(
            padre=None, slug="electronica", defaults={"nombre": "Electrónica"}
        )
        redes, _ = Categoria.objects.get_or_create(
            padre=electronica, slug="redes", defaults={"nombre": "Equipos de red"}
        )
        switches, _ = Categoria.objects.get_or_create(
            padre=redes, slug="switches", defaults={"nombre": "Switches"}
        )
        ferreteria, _ = Categoria.objects.get_or_create(
            padre=None, slug="ferreteria", defaults={"nombre": "Ferretería"}
        )

        # Atributos definidos en el nivel intermedio: los heredan los switches.
        for orden, (clave, etiqueta, tipo, unidad, opciones, obligatorio) in enumerate([
            ("puertos", "Cantidad de puertos", AtributoDefinicion.Tipo.NUMERO, "", [], True),
            ("velocidad", "Velocidad por puerto", AtributoDefinicion.Tipo.OPCION, "",
             ["100 Mbps", "1 Gbps", "10 Gbps"], True),
            ("administrable", "Administrable", AtributoDefinicion.Tipo.BOOLEANO, "", [], False),
            ("poe", "Soporte PoE", AtributoDefinicion.Tipo.BOOLEANO, "", [], False),
            ("temp_max", "Temperatura máxima de operación", AtributoDefinicion.Tipo.NUMERO,
             "°C", [], False),
        ]):
            AtributoDefinicion.objects.get_or_create(
                categoria=redes,
                clave=clave,
                defaults={"etiqueta": etiqueta, "tipo": tipo, "unidad": unidad,
                          "opciones": opciones, "obligatorio": obligatorio, "orden": orden},
            )

        # --- Productos ------------------------------------------------------
        # Complejo: hereda los atributos de "Equipos de red".
        switch, _ = Producto.objects.get_or_create(
            empresa=proveedora,
            slug="switch-gestionado-24p",
            defaults={
                "categoria": switches,
                "nombre": "Switch gestionado 24 puertos PoE+",
                "sku": "SW-24-POE",
                "descripcion_tecnica": "Switch capa 2+ de 24 puertos gigabit con PoE+ y 4 SFP.",
                "precio_unitario": Decimal("389990.00"),
                "moneda": "CLP",
                "cantidad_minima_pedido": 2,
                "unidad_empaque": "caja individual",
                "plazo_entrega_dias": 15,
                "stock_disponible": 40,
                "atributos": {
                    "puertos": 24,
                    "velocidad": "1 Gbps",
                    "administrable": True,
                    "poe": True,
                    "temp_max": 45,
                },
                "verificado": True,
                "publicado": True,
                "destacado": True,
            },
        )
        for volumen, precio in [(2, "389990.00"), (10, "365000.00"), (50, "339000.00")]:
            EscalaPrecio.objects.get_or_create(
                producto=switch, volumen_minimo=volumen,
                defaults={"precio_unitario": Decimal(precio)},
            )

        # Simple: categoría sin atributos definidos.
        Producto.objects.get_or_create(
            empresa=proveedora,
            slug="tornillo-autoperforante",
            defaults={
                "categoria": ferreteria,
                "nombre": "Tornillo autoperforante 8x1/2\"",
                "sku": "TOR-8-12",
                "precio_unitario": Decimal("18990.00"),
                "moneda": "CLP",
                "cantidad_minima_pedido": 10,
                "unidad_empaque": "caja de 1000 unidades",
                "plazo_entrega_dias": 5,
                "stock_disponible": 500,
                "publicado": True,
            },
        )

        self.stdout.write(self.style.SUCCESS(
            f"Demo lista: {Empresa.objects.count()} empresas, "
            f"{Categoria.objects.count()} categorías, {Producto.objects.count()} productos. "
            f"Compradora pendiente de verificar: {compradora.razon_social}."
        ))
