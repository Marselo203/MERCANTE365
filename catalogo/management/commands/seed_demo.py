"""
catalogo/management/commands/seed_demo.py

Datos ficticios para trabajar en el panel sin cargar todo a mano — cubre un
caso de cada módulo construido hasta ahora (Calificación, Red Comercial,
Oportunidades/Ventas/Comisiones, fotos de producto), no solo el catálogo
base. Las empresas proveedoras quedan en el norte de Chile (Antofagasta,
Iquique, Copiapó), a tono con el alcance geográfico actual del sitio.

    python manage.py seed_demo
    python manage.py seed_demo --limpiar   # borra lo anterior antes de recrear

NO lo corras en producción. Refuerza con DJANGO_DEBUG.
"""

import struct
import zlib
from datetime import date
from decimal import Decimal

from django.conf import settings
from django.core.files.base import ContentFile
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from catalogo.models import (
    AtributoDefinicion,
    Categoria,
    Ciudad,
    Comision,
    ContactoEmpresa,
    Empresa,
    EscalaPrecio,
    ImagenProducto,
    Oportunidad,
    Pais,
    Producto,
    Requerimiento,
    Vendedor,
    VendedorProducto,
    Venta,
)

VENDEDORES_DEMO = ["Carlos Rojas Comercial"]


def _png(color):
    """PNG de 4x4 de un color sólido — placeholder liviano para probar el
    módulo de fotos sin depender de un archivo de imagen real en disco."""
    def chunk(tag, data):
        return struct.pack(">I", len(data)) + tag + data + struct.pack(">I", zlib.crc32(tag + data))

    raw = b"".join(b"\x00" + bytes(color) * 4 for _ in range(4))
    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", struct.pack(">IIBBBBB", 4, 4, 8, 2, 0, 0, 0))
        + chunk(b"IDAT", zlib.compress(raw))
        + chunk(b"IEND", b"")
    )


class Command(BaseCommand):
    help = "Carga empresas, productos y datos de Calificación/Red Comercial/Ventas de demostración."

    def add_arguments(self, parser):
        parser.add_argument("--limpiar", action="store_true", help="Borra los datos demo previos.")

    @transaction.atomic
    def handle(self, *args, **opciones):
        if not settings.DEBUG:
            raise CommandError("seed_demo solo corre con DJANGO_DEBUG=1.")

        if not Pais.objects.exists():
            raise CommandError("Corre primero: python manage.py seed_ubicaciones")

        if opciones["limpiar"]:
            # Requerimiento.producto es PROTECT: hay que borrar los
            # requerimientos (y en cascada Oportunidad→Venta→Comision) ANTES
            # que los productos, si no la base rechaza el delete.
            Requerimiento.objects.filter(producto__empresa__slug__startswith="demo-").delete()
            Producto.objects.filter(empresa__slug__startswith="demo-").delete()
            Empresa.objects.filter(slug__startswith="demo-").delete()
            Vendedor.objects.filter(nombre__in=VENDEDORES_DEMO).delete()
            # Categoria.padre también es PROTECT (autorreferencia): un
            # `.all().delete()` de una sola vez falla apenas hay más de un
            # nivel, porque Django no sabe que la categoría padre se está por
            # borrar en la misma tanda. Hay que ir de las hojas hacia arriba.
            while Categoria.objects.exists():
                Categoria.objects.exclude(
                    pk__in=Categoria.objects.exclude(padre=None).values("padre")
                ).delete()
            self.stdout.write(self.style.WARNING("Datos demo anteriores eliminados."))

        # --- Ubicaciones ------------------------------------------------------
        santiago = Ciudad.objects.get(slug="santiago")
        la_paz = Ciudad.objects.get(slug="la-paz", region__pais="BO")
        antofagasta = Ciudad.objects.get(slug="antofagasta")
        iquique = Ciudad.objects.get(slug="iquique")
        copiapo = Ciudad.objects.get(slug="copiapo")

        # --- Empresas proveedoras: una por nivel comercial + estado de
        # calificación, para poder probar el filtro/gate de cada módulo -----
        andes, _ = Empresa.objects.update_or_create(
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
                "estado_verificacion": Empresa.EstadoVerificacion.VERIFICADA,
                "nivel_comercial": Empresa.NivelComercial.FREE,
                # Calificación completa: ejemplo de proveedor ya graduado.
                "chk_info_empresarial": True, "chk_contacto_revisado": True,
                "chk_direccion_registrada": True, "chk_sitio_web_revisado": True,
                "chk_info_comercial_revisada": True,
                "chk_producto_info_disponible": True, "chk_producto_fotos_disponibles": True,
                "chk_producto_ficha_tecnica": True, "chk_producto_marca_identificada": True,
                "chk_producto_info_comercial": True,
                "documentacion_estado": Empresa.DocumentacionEstado.REVISADA,
                "calificado": True,
            },
        )
        ContactoEmpresa.objects.get_or_create(
            empresa=andes,
            email="ventas@ejemplo-andes.cl",
            defaults={"nombre": "Carolina Soto", "cargo": "Jefa comercial",
                      "telefono": "+56 9 1234 5678", "es_principal": True},
        )

        mineros, _ = Empresa.objects.update_or_create(
            slug="demo-repuestos-mineros-norte",
            defaults={
                "rol": Empresa.Rol.PROVEEDORA,
                "razon_social": "Repuestos Mineros del Norte Ltda.",
                "nombre_comercial": "Repuestos Mineros del Norte",
                "identificador_tributario": "769876543",
                "pais_id": "CL",
                "region": antofagasta.region,
                "ciudad": antofagasta,
                "direccion_fisica": "Av. Balmaceda 2200, Antofagasta",
                "descripcion": "Repuestos y partes para equipos mineros e industriales.",
                "estado_verificacion": Empresa.EstadoVerificacion.VERIFICADA,
                "nivel_comercial": Empresa.NivelComercial.PYME,
                # Calificación a medio camino: ejemplo de proveedor en revisión.
                "chk_info_empresarial": True, "chk_contacto_revisado": True,
                "chk_producto_info_disponible": True,
                "documentacion_estado": Empresa.DocumentacionEstado.RECIBIDA,
                "calificado": False,
            },
        )

        puerto, _ = Empresa.objects.update_or_create(
            slug="demo-puerto-iquique-insumos",
            defaults={
                "rol": Empresa.Rol.PROVEEDORA,
                "razon_social": "Puerto Iquique Insumos Portuarios SpA",
                "nombre_comercial": "Puerto Iquique Insumos",
                "identificador_tributario": "762345678",
                "pais_id": "CL",
                "region": iquique.region,
                "ciudad": iquique,
                "direccion_fisica": "Zona Franca, Iquique",
                "descripcion": "Insumos y equipamiento para operación portuaria y logística.",
                "estado_verificacion": Empresa.EstadoVerificacion.VERIFICADA,
                "nivel_comercial": Empresa.NivelComercial.PREMIUM_PLUS,
                "chk_info_empresarial": True, "chk_contacto_revisado": True,
                "chk_direccion_registrada": True, "chk_sitio_web_revisado": True,
                "chk_info_comercial_revisada": True,
                "chk_producto_info_disponible": True, "chk_producto_fotos_disponibles": True,
                "chk_producto_ficha_tecnica": True, "chk_producto_marca_identificada": True,
                "chk_producto_info_comercial": True,
                "documentacion_estado": Empresa.DocumentacionEstado.REVISADA,
                "calificado": True,
            },
        )

        atacama, _ = Empresa.objects.update_or_create(
            slug="demo-ferreteria-atacama-express",
            defaults={
                "rol": Empresa.Rol.PROVEEDORA,
                "razon_social": "Ferretería Atacama Express Ltda.",
                "nombre_comercial": "Ferretería Atacama Express",
                "identificador_tributario": "770123456",
                "pais_id": "CL",
                "region": copiapo.region,
                "ciudad": copiapo,
                "direccion_fisica": "Av. Copayapu 800, Copiapó",
                "descripcion": "Ferretería industrial recién registrada en la plataforma.",
                "estado_verificacion": Empresa.EstadoVerificacion.NO_VERIFICADA,
                "nivel_comercial": Empresa.NivelComercial.FREE,
                # Sin nada de checklist todavía: recién se registró.
            },
        )

        # --- Empresas compradoras ---------------------------------------------
        illimani, _ = Empresa.objects.update_or_create(
            slug="demo-importadora-illimani",
            defaults={
                "rol": Empresa.Rol.COMPRADORA,
                "razon_social": "Importadora Illimani SRL",
                "identificador_tributario": "1023456789",
                "pais_id": "BO",
                "region": la_paz.region,
                "ciudad": la_paz,
                "direccion_fisica": "Av. Montes 500, La Paz",
                "estado_verificacion": Empresa.EstadoVerificacion.NO_VERIFICADA,
            },
        )
        norte_grande, _ = Empresa.objects.update_or_create(
            slug="demo-constructora-norte-grande",
            defaults={
                "rol": Empresa.Rol.COMPRADORA,
                "razon_social": "Constructora Norte Grande SpA",
                "identificador_tributario": "765432198",
                "pais_id": "CL",
                "region": antofagasta.region,
                "ciudad": antofagasta,
                "direccion_fisica": "Av. Argentina 1500, Antofagasta",
                "estado_verificacion": Empresa.EstadoVerificacion.VERIFICADA,
            },
        )

        # --- Categorías (3 niveles en electrónica; una por rubro nuevo) -------
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
        mineria, _ = Categoria.objects.get_or_create(
            padre=None, slug="mineria", defaults={"nombre": "Minería"}
        )
        repuestos, _ = Categoria.objects.get_or_create(
            padre=mineria, slug="repuestos-y-partes", defaults={"nombre": "Repuestos y partes"}
        )
        portuario, _ = Categoria.objects.get_or_create(
            padre=None, slug="puerto-y-logistica", defaults={"nombre": "Puerto y logística"}
        )

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
                categoria=redes, clave=clave,
                defaults={"etiqueta": etiqueta, "tipo": tipo, "unidad": unidad,
                          "opciones": opciones, "obligatorio": obligatorio, "orden": orden},
            )

        # --- Productos ----------------------------------------------------------
        switch, _ = Producto.objects.get_or_create(
            empresa=andes, slug="switch-gestionado-24p",
            defaults={
                "categoria": switches,
                "nombre": "Switch gestionado 24 puertos PoE+",
                "sku": "SW-24-POE",
                "descripcion_tecnica": "Switch capa 2+ de 24 puertos gigabit con PoE+ y 4 SFP.",
                "precio_unitario": Decimal("389990.00"), "moneda": "CLP",
                "cantidad_minima_pedido": 2, "unidad_empaque": "caja individual",
                "plazo_entrega_dias": 15, "stock_disponible": 40,
                "atributos": {"puertos": 24, "velocidad": "1 Gbps", "administrable": True,
                              "poe": True, "temp_max": 45},
                "estado_verificacion": Producto.EstadoVerificacion.VERIFICADO, "publicado": True, "destacado": True,
            },
        )
        for volumen, precio in [(2, "389990.00"), (10, "365000.00"), (50, "339000.00")]:
            EscalaPrecio.objects.get_or_create(
                producto=switch, volumen_minimo=volumen, defaults={"precio_unitario": Decimal(precio)},
            )

        Producto.objects.get_or_create(
            empresa=andes, slug="tornillo-autoperforante",
            defaults={
                "categoria": ferreteria, "nombre": "Tornillo autoperforante 8x1/2\"",
                "sku": "TOR-8-12", "precio_unitario": Decimal("18990.00"), "moneda": "CLP",
                "cantidad_minima_pedido": 10, "unidad_empaque": "caja de 1000 unidades",
                "plazo_entrega_dias": 5, "stock_disponible": 500, "publicado": True,
            },
        )

        bomba, _ = Producto.objects.get_or_create(
            empresa=mineros, slug="bomba-lodo-industrial-6x8",
            defaults={
                "categoria": repuestos, "nombre": "Bomba de lodo industrial 6x8",
                "sku": "BOM-6X8", "descripcion_tecnica": "Bomba centrífuga para faenas mineras, alta abrasión.",
                "precio_unitario": Decimal("4590000.00"), "moneda": "CLP",
                "cantidad_minima_pedido": 1, "unidad_empaque": "unidad",
                "plazo_entrega_dias": 30, "stock_disponible": 6,
                "estado_verificacion": Producto.EstadoVerificacion.VERIFICADO, "publicado": True, "destacado": True,
            },
        )
        Producto.objects.get_or_create(
            empresa=mineros, slug="filtro-hidraulico-industrial",
            defaults={
                "categoria": repuestos, "nombre": "Filtro hidráulico industrial",
                "sku": "FIL-HID-01", "precio_unitario": Decimal("89000.00"), "moneda": "CLP",
                "cantidad_minima_pedido": 4, "unidad_empaque": "caja de 4 unidades",
                "plazo_entrega_dias": 10, "stock_disponible": 60, "publicado": True,
            },
        )

        amarras, _ = Producto.objects.get_or_create(
            empresa=puerto, slug="cabo-amarre-portuario-40mm",
            defaults={
                "categoria": portuario, "nombre": "Cabo de amarre portuario 40mm",
                "sku": "CAB-40MM", "descripcion_tecnica": "Cabo de polipropileno de alta resistencia, rollo de 100m.",
                "precio_unitario": Decimal("612000.00"), "moneda": "CLP",
                "cantidad_minima_pedido": 1, "unidad_empaque": "rollo",
                "plazo_entrega_dias": 20, "stock_disponible": 15,
                "estado_verificacion": Producto.EstadoVerificacion.VERIFICADO, "publicado": True, "destacado": True,
            },
        )
        Producto.objects.get_or_create(
            empresa=puerto, slug="defensa-atraque-neumatica",
            defaults={
                "categoria": portuario, "nombre": "Defensa de atraque neumática",
                "sku": "DEF-ATR-01", "precio_unitario": Decimal("2150000.00"), "moneda": "CLP",
                "cantidad_minima_pedido": 1, "unidad_empaque": "unidad",
                "plazo_entrega_dias": 25, "stock_disponible": 8, "publicado": True,
            },
        )

        Producto.objects.get_or_create(
            empresa=atacama, slug="taladro-percutor-industrial",
            defaults={
                "categoria": ferreteria, "nombre": "Taladro percutor industrial 1100W",
                "sku": "TAL-1100", "precio_unitario": Decimal("129990.00"), "moneda": "CLP",
                "cantidad_minima_pedido": 1, "unidad_empaque": "unidad",
                "plazo_entrega_dias": 7, "stock_disponible": 20, "publicado": True,
            },
        )
        Producto.objects.get_or_create(
            empresa=atacama, slug="set-brocas-widia",
            defaults={
                "categoria": ferreteria, "nombre": "Set de brocas widia 10 piezas",
                "sku": "BRO-WID-10", "precio_unitario": Decimal("34990.00"), "moneda": "CLP",
                "cantidad_minima_pedido": 5, "unidad_empaque": "set",
                "plazo_entrega_dias": 5, "stock_disponible": 0,
                "publicado": False,  # todavía sin stock: en borrador
            },
        )

        # --- Fotos de producto: un color sólido por foto alcanza para probar
        # el módulo (subida, ordenar, marcar principal) sin depender de un
        # archivo de imagen real en disco. -------------------------------------
        for producto, color in [(switch, (13, 92, 187)), (bomba, (68, 167, 71)), (amarras, (255, 184, 0))]:
            if not producto.imagenes.filter(es_principal=True).exists():
                img = ImagenProducto(producto=producto, alt=producto.nombre, es_principal=True)
                img.imagen.save(f"{producto.slug}.png", ContentFile(_png(color)), save=True)

        # --- Red Comercial: vendedor + vinculación a un proveedor Premium Plus -
        carlos, _ = Vendedor.objects.get_or_create(
            nombre="Carlos Rojas Comercial",
            defaults={"whatsapp": "+56 9 8765 4321", "email": "carlos.rojas@ejemplo.cl",
                      "zona": "Norte Grande", "especialidad": "Minería e industria portuaria",
                      "comision": Decimal("8.00"), "estado": Vendedor.Estado.ACTIVO},
        )
        VendedorProducto.objects.get_or_create(
            vendedor=carlos, producto=amarras, defaults={"comision": Decimal("10.00")},
        )

        # --- Requerimientos: uno orgánico, uno atribuido al vendedor ------------
        req_organico, _ = Requerimiento.objects.get_or_create(
            producto=bomba, nombre_contacto="Marcela Fuentes", email_contacto="compras@ejemplo-cne.cl",
            defaults={"telefono_contacto": "+56 9 5555 1111", "empresa_compradora": norte_grande.razon_social,
                      "volumen_requerido": "2 unidades", "plazo_esperado": "45 días",
                      "estado": Requerimiento.Estado.EN_REVISION},
        )
        req_con_vendedor, _ = Requerimiento.objects.get_or_create(
            producto=amarras, nombre_contacto="Jorge Salinas", email_contacto="logistica@ejemplo-cne.cl",
            defaults={"telefono_contacto": "+56 9 5555 2222", "empresa_compradora": norte_grande.razon_social,
                      "volumen_requerido": "5 rollos", "plazo_esperado": "30 días",
                      "estado": Requerimiento.Estado.RESPONDIDO,
                      "origen": Requerimiento.Origen.VENDEDOR, "vendedor": carlos},
        )

        # --- Oportunidades / Venta / Comisión: una en curso, una ganada con
        # venta y comisión ya calculada sola. -------------------------------
        Oportunidad.objects.get_or_create(
            requerimiento=req_organico, defaults={"estado": Oportunidad.Estado.EN_NEGOCIACION},
        )
        oportunidad_ganada, _ = Oportunidad.objects.get_or_create(
            requerimiento=req_con_vendedor, defaults={"estado": Oportunidad.Estado.GANADA},
        )
        if not hasattr(oportunidad_ganada, "venta"):
            Venta.objects.create(
                oportunidad=oportunidad_ganada, monto=Decimal("3060000.00"),
                comprobante_externo="F-000123", fecha=date.today(),
                observaciones="5 rollos de cabo de amarre 40mm.",
            )
        if hasattr(oportunidad_ganada, "venta"):
            comision = Comision.objects.filter(venta=oportunidad_ganada.venta).first()
            if comision:
                comision.estado = Comision.Estado.CONFIRMADA
                comision.save()

        self.stdout.write(self.style.SUCCESS(
            f"Demo lista: {Empresa.objects.filter(slug__startswith='demo-').count()} empresas demo, "
            f"{Categoria.objects.count()} categorías, "
            f"{Producto.objects.filter(empresa__slug__startswith='demo-').count()} productos demo, "
            f"{Vendedor.objects.count()} vendedor(es), "
            f"{Requerimiento.objects.count()} requerimiento(s), "
            f"{Comision.objects.count()} comisión(es) calculada(s)."
        ))
