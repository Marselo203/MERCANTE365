"""Agrega al grupo "Staff completo" (creado en 0009) los permisos de los
3 modelos nuevos de esta migración (Oportunidad, Venta, Comision) — si no,
un staff no-superuser que ya estaba en ese grupo se quedaría sin acceso a
las secciones nuevas del menú (Oportunidades/Ventas/Comisiones)."""

from django.db import migrations

CODENAMES = [
    "add_oportunidad", "change_oportunidad", "delete_oportunidad", "view_oportunidad",
    "add_venta", "change_venta", "delete_venta", "view_venta",
    "add_comision", "change_comision", "delete_comision", "view_comision",
]

NOMBRE_GRUPO = "Staff completo"


def agregar_permisos(apps, schema_editor):
    from django.apps import apps as apps_reales
    from django.contrib.auth.management import create_permissions

    for app_config in apps_reales.get_app_configs():
        create_permissions(app_config, verbosity=0)

    Group = apps.get_model("auth", "Group")
    Permission = apps.get_model("auth", "Permission")

    grupo, _ = Group.objects.get_or_create(name=NOMBRE_GRUPO)
    grupo.permissions.add(*Permission.objects.filter(codename__in=CODENAMES))


def quitar_permisos(apps, schema_editor):
    Group = apps.get_model("auth", "Group")
    Permission = apps.get_model("auth", "Permission")
    try:
        grupo = Group.objects.get(name=NOMBRE_GRUPO)
    except Group.DoesNotExist:
        return
    grupo.permissions.remove(*Permission.objects.filter(codename__in=CODENAMES))


class Migration(migrations.Migration):
    dependencies = [
        ("catalogo", "0010_oportunidad_venta_comision"),
        ("catalogo", "0009_grupo_staff_completo"),
    ]

    operations = [
        migrations.RunPython(agregar_permisos, quitar_permisos),
    ]
