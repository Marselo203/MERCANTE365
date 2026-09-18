"""Permisos finos en el panel (panel/views.py::_Base.test_func): cada recurso
puede declarar un "permiso" de Django que lo gatea. Para que este cambio NO le
saque acceso a ningún staff existente, se crea un grupo "Staff completo" con
todos los permisos relevantes y se mete ahí a todo el staff actual (no
superusers, que ya pasan cualquier chequeo de permiso). De acá en más, un
staff nuevo con un rol más acotado se crea en un grupo aparte con menos
permisos — eso se gestiona desde /django-admin/ (Usuarios y grupos), no hace
falta código nuevo para eso."""

from django.db import migrations

CODENAMES = [
    "add_producto", "change_producto", "delete_producto", "view_producto",
    "add_empresa", "change_empresa", "delete_empresa", "view_empresa",
    "gestionar_proveedores", "gestionar_compradores", "gestionar_calificacion",
    "add_categoria", "change_categoria", "delete_categoria", "view_categoria",
    "add_atributodefinicion", "change_atributodefinicion",
    "delete_atributodefinicion", "view_atributodefinicion",
    "add_imagenproducto", "change_imagenproducto", "delete_imagenproducto", "view_imagenproducto",
    "add_escalaprecio", "change_escalaprecio", "delete_escalaprecio", "view_escalaprecio",
    "add_contactoempresa", "change_contactoempresa", "delete_contactoempresa", "view_contactoempresa",
    "add_requerimiento", "change_requerimiento", "delete_requerimiento", "view_requerimiento",
    "add_vendedor", "change_vendedor", "delete_vendedor", "view_vendedor",
    "add_vendedorproducto", "change_vendedorproducto",
    "delete_vendedorproducto", "view_vendedorproducto",
]

NOMBRE_GRUPO = "Staff completo"


def crear_grupo(apps, schema_editor):
    # Los Permission de los codenames de arriba recién existen en la base
    # después del post_migrate de esta misma corrida de `migrate` — hay que
    # forzar su creación acá para poder asignarlos ya (patrón documentado por
    # Django para migraciones de datos que tocan permisos).
    from django.apps import apps as apps_reales
    from django.contrib.auth.management import create_permissions

    for app_config in apps_reales.get_app_configs():
        create_permissions(app_config, verbosity=0)

    Group = apps.get_model("auth", "Group")
    Permission = apps.get_model("auth", "Permission")
    User = apps.get_model("auth", "User")

    grupo, _ = Group.objects.get_or_create(name=NOMBRE_GRUPO)
    grupo.permissions.set(Permission.objects.filter(codename__in=CODENAMES))

    for user in User.objects.filter(is_staff=True, is_superuser=False):
        user.groups.add(grupo)


def eliminar_grupo(apps, schema_editor):
    apps.get_model("auth", "Group").objects.filter(name=NOMBRE_GRUPO).delete()


class Migration(migrations.Migration):
    dependencies = [
        ("catalogo", "0008_alter_empresa_options"),
        ("auth", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(crear_grupo, eliminar_grupo),
    ]
