"""
catalogo/management/commands/seed_ubicaciones.py

Carga países, regiones/departamentos y ciudades principales de Chile y Bolivia.
Idempotente: puedes correrlo las veces que quieras sin duplicar nada.

    python manage.py seed_ubicaciones
"""

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils.text import slugify

from catalogo.models import Ciudad, Pais, Region

CHILE = {
    "Arica y Parinacota": ["Arica"],
    "Tarapacá": ["Iquique", "Alto Hospicio"],
    "Antofagasta": ["Antofagasta", "Calama"],
    "Atacama": ["Copiapó", "Vallenar"],
    "Coquimbo": ["La Serena", "Coquimbo", "Ovalle"],
    "Valparaíso": ["Valparaíso", "Viña del Mar", "Quilpué", "San Antonio"],
    "Metropolitana de Santiago": ["Santiago", "Puente Alto", "Maipú", "Quilicura"],
    "Libertador General Bernardo O'Higgins": ["Rancagua", "San Fernando"],
    "Maule": ["Talca", "Curicó", "Linares"],
    "Ñuble": ["Chillán"],
    "Biobío": ["Concepción", "Talcahuano", "Los Ángeles"],
    "La Araucanía": ["Temuco", "Villarrica"],
    "Los Ríos": ["Valdivia", "La Unión"],
    "Los Lagos": ["Puerto Montt", "Osorno", "Castro"],
    "Aysén del General Carlos Ibáñez del Campo": ["Coyhaique", "Puerto Aysén"],
    "Magallanes y de la Antártica Chilena": ["Punta Arenas", "Puerto Natales"],
}

BOLIVIA = {
    "La Paz": ["La Paz", "El Alto", "Viacha", "Achocalla"],
    "Santa Cruz": ["Santa Cruz de la Sierra", "Montero", "Warnes", "La Guardia"],
    "Cochabamba": ["Cochabamba", "Quillacollo", "Sacaba", "Colcapirhua"],
    "Oruro": ["Oruro", "Huanuni"],
    "Potosí": ["Potosí", "Llallagua", "Uyuni"],
    "Chuquisaca": ["Sucre", "Monteagudo"],
    "Tarija": ["Tarija", "Yacuiba", "Bermejo"],
    "Beni": ["Trinidad", "Riberalta", "Guayaramerín"],
    "Pando": ["Cobija"],
}


class Command(BaseCommand):
    help = "Carga la división político-administrativa de Chile y Bolivia."

    @transaction.atomic
    def handle(self, *args, **opciones):
        totales = {"paises": 0, "regiones": 0, "ciudades": 0}

        for codigo, nombre, datos in (
            ("CL", "Chile", CHILE),
            ("BO", "Bolivia", BOLIVIA),
        ):
            pais, creado = Pais.objects.get_or_create(
                codigo_iso=codigo, defaults={"nombre": nombre}
            )
            totales["paises"] += int(creado)

            for nombre_region, ciudades in datos.items():
                region, creado = Region.objects.get_or_create(
                    pais=pais,
                    slug=slugify(nombre_region)[:140],
                    defaults={"nombre": nombre_region},
                )
                totales["regiones"] += int(creado)

                for nombre_ciudad in ciudades:
                    _, creado = Ciudad.objects.get_or_create(
                        region=region,
                        slug=slugify(nombre_ciudad)[:140],
                        defaults={"nombre": nombre_ciudad},
                    )
                    totales["ciudades"] += int(creado)

        self.stdout.write(
            self.style.SUCCESS(
                f"Nuevos: {totales['paises']} países, "
                f"{totales['regiones']} regiones, {totales['ciudades']} ciudades. "
                f"Totales en base: {Pais.objects.count()} / "
                f"{Region.objects.count()} / {Ciudad.objects.count()}."
            )
        )
