"""
catalogo/models.py — modelos del catálogo B2B.

El contrato exacto (campos, choices, unicidades) sale de los dos seeds en
management/commands/. La herencia de atributos se resuelve caminando la cadena
de `padre`; no hay ruta materializada todavía.

Los `help_text` de los campos son los que se muestran como ayuda en cada
formulario del panel de gestión (ver panel/templates/panel/form.html) — es la
única fuente, no hay textos duplicados en las plantillas.
"""

import io
import os

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.files.base import ContentFile
from django.db import models
from django.utils.text import slugify
from PIL import Image, ImageOps


# --- Ubicaciones ---------------------------------------------------------------

class Pais(models.Model):
    codigo_iso = models.CharField("código ISO", max_length=2, primary_key=True)
    nombre = models.CharField(max_length=80)

    class Meta:
        verbose_name = "país"
        verbose_name_plural = "países"
        ordering = ["nombre"]

    def __str__(self):
        return self.nombre


class Region(models.Model):
    pais = models.ForeignKey(Pais, on_delete=models.PROTECT, related_name="regiones")
    nombre = models.CharField(max_length=120)
    slug = models.SlugField(max_length=140)

    class Meta:
        verbose_name = "región"
        verbose_name_plural = "regiones"
        ordering = ["pais", "nombre"]
        constraints = [
            models.UniqueConstraint(fields=["pais", "slug"], name="region_slug_unico_por_pais"),
        ]

    def __str__(self):
        return f"{self.nombre}, {self.pais_id}"


class Ciudad(models.Model):
    region = models.ForeignKey(Region, on_delete=models.PROTECT, related_name="ciudades")
    nombre = models.CharField(max_length=120)
    slug = models.SlugField(max_length=140)

    class Meta:
        verbose_name = "ciudad"
        verbose_name_plural = "ciudades"
        ordering = ["nombre"]
        constraints = [
            models.UniqueConstraint(fields=["region", "slug"], name="ciudad_slug_unico_por_region"),
        ]

    def __str__(self):
        return self.nombre


# --- Empresas ----------------------------------------------------------------

class Empresa(models.Model):
    class Rol(models.TextChoices):
        PROVEEDORA = "proveedora", "Proveedora"
        COMPRADORA = "compradora", "Compradora"

    class EstadoVerificacion(models.TextChoices):
        """Insignia pública «Empresa Verificada» (documento de membresías,
        secciones 10.5-10.8) — antes tenía solo 3 estados (Pendiente/Aprobada/
        Rechazada), ahora son los 5 del documento. No confundir con
        `calificado`/el checklist de Calificación: esta insignia reusa esa
        misma tarea de revisión ya hecha (legalidad, contacto, documentación)
        como su evidencia, no duplica un segundo checklist idéntico — el
        estado de acá es el veredicto final que decide el admin, informado
        por ese checklist."""
        NO_VERIFICADA = "no_verificada", "No verificada"
        EN_REVISION = "en_revision", "En revisión"
        VERIFICADA = "verificada", "Verificada"
        OBSERVADA = "observada", "Observada"
        SUSPENDIDA = "suspendida", "Suspendida"

    rol = models.CharField(
        max_length=12, choices=Rol.choices,
        help_text="Proveedora si vende productos en el catálogo; Compradora si va a enviar requerimientos.",
    )
    razon_social = models.CharField(
        max_length=200,
        help_text="Nombre legal completo, como figura en sus documentos tributarios.",
    )
    nombre_comercial = models.CharField(
        max_length=200, blank=True,
        help_text="Nombre con el que se muestra en el catálogo público. Si lo dejás vacío, se usa la razón social.",
    )
    identificador_tributario = models.CharField(
        max_length=32, help_text="RUT (Chile) o NIT (Bolivia) de la empresa, sin puntos ni guiones.",
    )
    slug = models.SlugField(
        max_length=140, unique=True, blank=True,
        help_text="Parte de la URL pública de la empresa. Minúsculas y guiones, sin espacios ni tildes. "
        "Se genera solo desde la razón social si lo dejás vacío.",
    )
    usuario = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="empresa",
        help_text="La cuenta con la que esta empresa entra a su panel de autoservicio "
        "(solo proveedoras, por ahora). Vacío para empresas cargadas desde el back office.",
    )

    pais = models.ForeignKey(
        Pais, on_delete=models.PROTECT, help_text="País donde está constituida la empresa.",
    )
    region = models.ForeignKey(
        Region, on_delete=models.PROTECT,
        help_text="Región (Chile) o departamento (Bolivia) de la empresa.",
    )
    ciudad = models.ForeignKey(
        Ciudad, on_delete=models.PROTECT,
        help_text="Ciudad donde opera la empresa; tiene que pertenecer a la región elegida.",
    )
    direccion_fisica = models.CharField(
        max_length=255, blank=True,
        help_text="Dirección física. Es opcional y no se muestra en el catálogo público.",
    )
    descripcion = models.TextField(
        blank=True, help_text="Texto breve sobre la empresa para su ficha pública (opcional).",
    )
    logo = models.ImageField(
        upload_to="empresas/logos/", blank=True,
        help_text="Logo de la empresa para su perfil público (opcional).",
    )

    estado_verificacion = models.CharField(
        max_length=15, choices=EstadoVerificacion.choices, default=EstadoVerificacion.NO_VERIFICADA,
        help_text="Pasala a Verificada recién cuando MERCANTE365 completó la revisión — nunca se "
        "otorga automáticamente por contratar una membresía. La insignia pública solo se muestra "
        "si además el plan es PYME o superior (en Free no aplica).",
    )
    creada = models.DateTimeField(auto_now_add=True)

    # --- Calificación del proveedor (checklist administrado por MERCANTE365,
    # nunca autodeclarado por el proveedor — documento de producto, sección 32) --
    class DocumentacionEstado(models.TextChoices):
        PENDIENTE = "pendiente", "Pendiente"
        RECIBIDA = "recibida", "Recibida"
        REVISADA = "revisada", "Revisada"

    CHECKLIST_CALIFICACION = [
        "chk_info_empresarial", "chk_contacto_revisado", "chk_direccion_registrada",
        "chk_sitio_web_revisado", "chk_info_comercial_revisada",
        "chk_producto_info_disponible", "chk_producto_fotos_disponibles",
        "chk_producto_ficha_tecnica", "chk_producto_marca_identificada",
        "chk_producto_info_comercial",
    ]

    chk_info_empresarial = models.BooleanField("Información empresarial revisada", default=False)
    chk_contacto_revisado = models.BooleanField("Contacto revisado", default=False)
    chk_direccion_registrada = models.BooleanField("Dirección registrada", default=False)
    chk_sitio_web_revisado = models.BooleanField("Sitio web revisado", default=False)
    chk_info_comercial_revisada = models.BooleanField("Información comercial revisada", default=False)
    chk_producto_info_disponible = models.BooleanField("Producto: información disponible", default=False)
    chk_producto_fotos_disponibles = models.BooleanField("Producto: fotografías disponibles", default=False)
    chk_producto_ficha_tecnica = models.BooleanField("Producto: ficha técnica", default=False)
    chk_producto_marca_identificada = models.BooleanField("Producto: marca identificada", default=False)
    chk_producto_info_comercial = models.BooleanField("Producto: información comercial", default=False)
    documentacion_estado = models.CharField(
        max_length=10, choices=DocumentacionEstado.choices, default=DocumentacionEstado.PENDIENTE,
    )
    calificado = models.BooleanField(
        "Proveedor calificado", default=False,
        help_text="Solo lo marca MERCANTE365 desde este panel, nunca el proveedor: "
        "revisá el checklist completo antes de activarlo.",
    )

    class NivelComercial(models.TextChoices):
        FREE = "free", "Free"
        PYME = "pyme", "PYME"
        PREMIUM = "premium", "Premium"
        PREMIUM_PLUS = "premium_plus", "Premium Plus"

    # Documento "Especificación funcional para configuración de membresías",
    # secciones 2 y 15: límite de productos ACTIVOS (=publicados) por nivel,
    # y su orden para poder detectar un downgrade. Todavía sin pagos ni panel
    # de autoservicio (prioridad 1 del documento, fuera de este alcance): el
    # admin cambia el nivel a mano desde el panel, como ya hace con la
    # verificación.
    LIMITE_PRODUCTOS = {
        NivelComercial.FREE: 3, NivelComercial.PYME: 7,
        NivelComercial.PREMIUM: 150, NivelComercial.PREMIUM_PLUS: 300,
    }
    ORDEN_NIVEL = {
        NivelComercial.FREE: 0, NivelComercial.PYME: 1,
        NivelComercial.PREMIUM: 2, NivelComercial.PREMIUM_PLUS: 3,
    }

    nivel_comercial = models.CharField(
        max_length=12, choices=NivelComercial.choices, default=NivelComercial.FREE,
        help_text="Define cuántos productos activos puede tener esta empresa (Free 3 · PYME 7 · "
        "Premium 150 · Premium Plus 300). Si la bajás y tiene más productos publicados que el "
        "nuevo límite, los más nuevos se desactivan solos (quedan guardados, no se borran). "
        "Premium Plus además habilita vincularse a un vendedor de la Red Comercial.",
    )

    class Meta:
        verbose_name = "empresa"
        ordering = ["razon_social"]
        permissions = [
            ("gestionar_proveedores", "Puede gestionar proveedores"),
            ("gestionar_compradores", "Puede gestionar compradores"),
            ("gestionar_calificacion", "Puede gestionar la calificación de proveedores"),
        ]

    def __str__(self):
        return self.nombre_comercial or self.razon_social

    def progreso_checklist(self):
        total = len(self.CHECKLIST_CALIFICACION)
        hechos = sum(1 for campo in self.CHECKLIST_CALIFICACION if getattr(self, campo))
        return f"{hechos}/{total}"

    def limite_productos(self):
        return self.LIMITE_PRODUCTOS[self.nivel_comercial]

    @property
    def es_verificada(self):
        """Insignia pública «✓ Empresa Verificada» — requiere el estado Y el
        plan PYME o superior (documento de membresías, sección 10.5)."""
        return (
            self.estado_verificacion == self.EstadoVerificacion.VERIFICADA
            and self.nivel_comercial != self.NivelComercial.FREE
        )

    def productos_activos_count(self):
        return self.productos.filter(publicado=True).count()

    def save(self, *args, **kw):
        # Mismo tratamiento que las fotos de producto: un logo de 4 MB pesa
        # igual en la ficha pública que una foto de 4 MB (ver `reducir_imagen`).
        if self.logo and not self.logo._committed:
            reducido = reducir_imagen(self.logo)
            if reducido is not None:
                self.logo = reducido

        if not self.slug:
            base = slugify(self.razon_social)[:130]
            slug, sufijo = base, 1
            while Empresa.objects.exclude(pk=self.pk).filter(slug=slug).exists():
                sufijo += 1
                slug = f"{base}-{sufijo}"
            self.slug = slug

        bajo_de_nivel = False
        if self.pk:
            nivel_anterior = Empresa.objects.filter(pk=self.pk).values_list(
                "nivel_comercial", flat=True
            ).first()
            if nivel_anterior and self.ORDEN_NIVEL[nivel_anterior] > self.ORDEN_NIVEL[self.nivel_comercial]:
                bajo_de_nivel = True
        super().save(*args, **kw)
        self._productos_archivados = 0
        if bajo_de_nivel:
            self._productos_archivados = self._archivar_productos_excedentes()

    def _archivar_productos_excedentes(self):
        """Al bajar de nivel, los productos que excedan el nuevo límite se
        desactivan (no se borran) — el más antiguo activo queda, los más
        nuevos se archivan primero, criterio propio: se listaron después,
        se asume que el listado viejo es el más consolidado."""
        limite = self.limite_productos()
        activos = list(self.productos.filter(publicado=True).order_by("creado"))
        excedentes = activos[limite:]
        for producto in excedentes:
            producto.publicado = False
            producto.save(update_fields=["publicado"])
        return len(excedentes)


class ContactoEmpresa(models.Model):
    empresa = models.ForeignKey(
        Empresa, on_delete=models.CASCADE, related_name="contactos",
        help_text="Empresa a la que pertenece este contacto.",
    )
    nombre = models.CharField(max_length=120, help_text="Nombre de la persona de contacto.")
    cargo = models.CharField(
        max_length=120, blank=True, help_text="Cargo dentro de la empresa (opcional).",
    )
    email = models.EmailField(
        help_text="Correo de contacto. No puede repetirse dentro de la misma empresa.",
    )
    telefono = models.CharField(
        max_length=40, blank=True, help_text="Teléfono de contacto, con código de país si es posible.",
    )
    es_principal = models.BooleanField(
        default=False,
        help_text="Solo puede haber un contacto principal por empresa; es el que se muestra en el catálogo público.",
    )

    class Meta:
        verbose_name = "contacto de empresa"
        verbose_name_plural = "contactos de empresa"
        constraints = [
            models.UniqueConstraint(
                fields=["empresa", "email"], name="contacto_email_unico_por_empresa"
            ),
            models.UniqueConstraint(
                fields=["empresa"],
                condition=models.Q(es_principal=True),
                name="un_contacto_principal_por_empresa",
            ),
        ]

    def __str__(self):
        return f"{self.nombre} <{self.email}>"


# --- Categorías y atributos --------------------------------------------------

class Categoria(models.Model):
    padre = models.ForeignKey(
        "self", on_delete=models.PROTECT, null=True, blank=True, related_name="hijas",
        help_text="Categoría superior, si esta es una subcategoría. Dejalo vacío si es un rubro principal.",
    )
    nombre = models.CharField(max_length=140, help_text="Nombre visible de la categoría en el catálogo.")
    slug = models.SlugField(
        max_length=140,
        help_text="Parte de la URL para filtrar por esta categoría. Minúsculas y guiones, sin espacios.",
    )

    class Meta:
        verbose_name = "categoría"
        verbose_name_plural = "categorías"
        ordering = ["nombre"]
        constraints = [
            models.UniqueConstraint(fields=["padre", "slug"], name="categoria_slug_unico_por_padre"),
            models.UniqueConstraint(
                fields=["slug"],
                condition=models.Q(padre__isnull=True),
                name="categoria_raiz_slug_unico",
            ),
        ]

    def __str__(self):
        return " / ".join(c.nombre for c in self.cadena())

    def cadena(self):
        """De la raíz hasta esta categoría, inclusive."""
        nodo, camino = self, []
        while nodo is not None:
            camino.append(nodo)
            nodo = nodo.padre
        return camino[::-1]

    def atributos_heredados(self):
        """Definiciones de esta categoría y de sus ancestras; si una clave se
        repite, gana la más cercana. Ordenadas por (orden, clave)."""
        por_clave = {}
        for cat in self.cadena()[::-1]:  # de la actual hacia arriba
            for ad in cat.atributos.all():
                por_clave.setdefault(ad.clave, ad)
        return sorted(por_clave.values(), key=lambda ad: (ad.orden, ad.clave))

    @classmethod
    def arbol(cls):
        """{id: [ese id + todos sus descendientes]} para TODO el árbol, en una
        sola query. La tabla de categorías es chica (decenas de filas): traerla
        entera y resolver la jerarquía en Python sale mucho más barato que una
        query por nodo, que es lo que costaba recorrer `hijas` recursivamente."""
        hijas = {}
        nodos = list(cls.objects.values_list("pk", "padre_id"))
        for pk, padre_id in nodos:
            hijas.setdefault(padre_id, []).append(pk)

        def bajar(pk):
            ids = [pk]
            for hija in hijas.get(pk, ()):
                ids += bajar(hija)
            return ids

        return {pk: bajar(pk) for pk, _ in nodos}

    def con_descendientes(self):
        """IDs de esta categoría y de todas sus hijas, recursivo. Para filtrar
        productos por un rubro que puede tener subcategorías."""
        return self.arbol().get(self.pk, [self.pk])


class AtributoDefinicion(models.Model):
    class Tipo(models.TextChoices):
        NUMERO = "numero", "Número"
        OPCION = "opcion", "Opción"
        BOOLEANO = "booleano", "Booleano"
        TEXTO = "texto", "Texto"

    categoria = models.ForeignKey(
        Categoria, on_delete=models.CASCADE, related_name="atributos",
        help_text="Categoría donde se define este atributo. Sus subcategorías también lo heredan.",
    )
    clave = models.SlugField(
        max_length=60,
        help_text="Identificador interno sin espacios; es la clave que se usa en el campo "
        "'Atributos' de cada producto.",
    )
    etiqueta = models.CharField(
        max_length=120, help_text="Nombre visible del atributo en la ficha del producto.",
    )
    tipo = models.CharField(
        max_length=10, choices=Tipo.choices,
        help_text="Tipo de dato esperado: número, una opción de una lista, sí/no, o texto libre.",
    )
    unidad = models.CharField(
        max_length=20, blank=True,
        help_text="Unidad a mostrar junto al valor, por ejemplo 'Gbps' o '°C' (opcional).",
    )
    opciones = models.JSONField(
        default=list, blank=True,
        help_text='Solo para tipo Opción: lista de valores válidos en JSON. '
        'Ejemplo: ["1 Gbps", "10 Gbps"].',
    )
    obligatorio = models.BooleanField(
        default=False,
        help_text="Si está marcado, todo producto de esta categoría debe incluir este atributo.",
    )
    orden = models.PositiveSmallIntegerField(
        default=0, help_text="Controla el orden en que aparece respecto a los demás atributos de la categoría.",
    )

    class Meta:
        verbose_name = "definición de atributo"
        verbose_name_plural = "definiciones de atributo"
        ordering = ["categoria", "orden", "clave"]
        constraints = [
            models.UniqueConstraint(
                fields=["categoria", "clave"], name="atributo_clave_unica_por_categoria"
            ),
        ]

    def __str__(self):
        return f"{self.etiqueta} ({self.clave})"

    def error_de_valor(self, valor):
        """Mensaje si `valor` no encaja con este tipo; None si está bien."""
        t = self.Tipo
        if self.tipo == t.BOOLEANO and not isinstance(valor, bool):
            return f"'{self.clave}' espera un booleano."
        if self.tipo == t.NUMERO and (isinstance(valor, bool) or not isinstance(valor, (int, float))):
            return f"'{self.clave}' espera un número."
        if self.tipo == t.TEXTO and not isinstance(valor, str):
            return f"'{self.clave}' espera texto."
        if self.tipo == t.OPCION and valor not in self.opciones:
            return f"'{self.clave}': '{valor}' no está entre {self.opciones}."
        return None


# --- Productos -------------------------------------------------------------

class Producto(models.Model):
    class EstadoVerificacion(models.TextChoices):
        """Insignia pública «Producto Verificado» (documento de membresías,
        secciones 10.9-10.11) — antes era un simple booleano `verificado`.
        Independiente de si la empresa está verificada (sección 10.12)."""
        NO_VERIFICADO = "no_verificado", "No verificado"
        EN_REVISION = "en_revision", "En revisión"
        VERIFICADO = "verificado", "Verificado"
        OBSERVADO = "observado", "Observado"
        SUSPENDIDO = "suspendido", "Suspendido"

    empresa = models.ForeignKey(
        Empresa, on_delete=models.CASCADE, related_name="productos",
        help_text="Empresa proveedora dueña de este producto.",
    )
    categoria = models.ForeignKey(
        Categoria, on_delete=models.PROTECT, related_name="productos",
        help_text="Categoría del producto. De ella hereda los atributos técnicos de más abajo.",
    )
    nombre = models.CharField(max_length=200, help_text="Nombre del producto tal como se muestra en el catálogo.")
    slug = models.SlugField(
        max_length=140,
        help_text="Parte de la URL del producto. Minúsculas y guiones; no se repite dentro de la misma empresa.",
    )
    sku = models.CharField(max_length=60, blank=True, help_text="Código interno del proveedor (opcional).")
    descripcion_tecnica = models.TextField(
        blank=True, help_text="Descripción técnica que se muestra en la ficha pública del producto.",
    )

    precio_unitario = models.DecimalField(
        max_digits=14, decimal_places=2, help_text="Precio por unidad, en la moneda indicada abajo.",
    )
    moneda = models.CharField(max_length=3, default="CLP", help_text="Código de la moneda del precio, por ejemplo CLP o USD.")
    cantidad_minima_pedido = models.PositiveIntegerField(
        default=1, help_text="Cantidad mínima que un comprador tiene que pedir.",
    )
    unidad_empaque = models.CharField(
        max_length=60, blank=True, help_text="Cómo viene empaquetado, por ejemplo 'caja de 12' (opcional).",
    )
    plazo_entrega_dias = models.PositiveSmallIntegerField(
        default=0, help_text="Días hábiles estimados de despacho desde que se confirma el pedido.",
    )
    stock_disponible = models.PositiveIntegerField(default=0, help_text="Unidades disponibles actualmente.")

    atributos = models.JSONField(
        default=dict, blank=True,
        help_text="Valores técnicos en JSON, con las claves definidas en la categoría. "
        'Ejemplo: {"puertos": 24, "poe": true}.',
    )

    estado_verificacion = models.CharField(
        max_length=15, choices=EstadoVerificacion.choices, default=EstadoVerificacion.NO_VERIFICADO,
        help_text="Pasalo a Verificado cuando el equipo corroboró la información con el proveedor. "
        "La insignia pública solo se muestra si además la empresa tiene plan PYME o superior.",
    )
    publicado = models.BooleanField(default=False, help_text="Solo los productos publicados se muestran en el catálogo público.")
    destacado = models.BooleanField(default=False, help_text="Los productos destacados aparecen en la portada del sitio.")
    creado = models.DateTimeField(auto_now_add=True)
    actualizado = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "producto"
        verbose_name_plural = "productos"
        ordering = ["-creado"]
        constraints = [
            models.UniqueConstraint(
                fields=["empresa", "slug"], name="producto_slug_unico_por_empresa"
            ),
        ]

    def __str__(self):
        return self.nombre

    @property
    def imagen_principal(self):
        # `imagenes.all()` reusa el prefetch_related de la vista cuando lo hay;
        # el `ordering` del Meta ya pone la principal primera. Con `.filter()`
        # acá era una query por producto en cada grilla del catálogo.
        return next(iter(self.imagenes.all()), None)

    @property
    def es_verificado(self):
        """Insignia pública «✓ Producto Verificado» — requiere el estado Y
        que la empresa tenga plan PYME o superior (sección 10.9)."""
        return (
            self.estado_verificacion == self.EstadoVerificacion.VERIFICADO
            and self.empresa.nivel_comercial != Empresa.NivelComercial.FREE
        )

    def clean(self):
        """Valida el límite de productos activos del plan de la empresa
        (documento de membresías, sección 15) y `atributos` contra las
        definiciones heredadas de la categoría: rechaza claves no definidas,
        tipos equivocados, opciones fuera de lista y faltantes obligatorios."""
        if self.publicado and self.empresa_id:
            limite = self.empresa.limite_productos()
            activos = self.empresa.productos.filter(publicado=True).exclude(pk=self.pk).count()
            if activos >= limite:
                raise ValidationError({
                    "publicado": f"Esta empresa ya tiene {activos} producto{'s' if activos != 1 else ''} "
                    f"activo{'s' if activos != 1 else ''} — el máximo de su plan "
                    f"({self.empresa.get_nivel_comercial_display()}) es {limite}. Desactivá otro "
                    "producto o subí de plan para publicar este.",
                })

        if self.categoria_id is None:
            return
        if not isinstance(self.atributos, dict):
            raise ValidationError({"atributos": "Debe ser un objeto JSON."})

        definiciones = {ad.clave: ad for ad in self.categoria.atributos_heredados()}
        errores = []
        for clave, valor in self.atributos.items():
            ad = definiciones.get(clave)
            if ad is None:
                errores.append(f"'{clave}' no está definida en la categoría «{self.categoria}».")
                continue
            msg = ad.error_de_valor(valor)
            if msg:
                errores.append(msg)
        for clave, ad in definiciones.items():
            if ad.obligatorio and clave not in self.atributos:
                errores.append(f"Falta el atributo obligatorio '{clave}'.")

        if errores:
            raise ValidationError({"atributos": errores})


LADO_MAXIMO_IMAGEN = 1600
FORMATOS_REDIMENSIONABLES = {"JPEG", "PNG", "WEBP"}


def reducir_imagen(campo, lado=LADO_MAXIMO_IMAGEN):
    """La foto reescalada a `lado` px de lado mayor, o None si ya entra y no
    hay nada que hacer.

    Una foto de celular son 3-5 MB y 4000 px de ancho; la tarjeta del catálogo
    la muestra a 400. Sin esto, cada vista del Market bajaba decenas de MB
    desde Object Storage al teléfono del comprador. Se conserva el formato
    original (un PNG sigue siendo PNG) para no cambiar la extensión del
    archivo ni perder transparencias."""
    campo.open()
    imagen = Image.open(campo.file)
    formato = imagen.format
    if formato not in FORMATOS_REDIMENSIONABLES or max(imagen.size) <= lado:
        return None

    nombre, extension = os.path.splitext(os.path.basename(campo.name))
    # Un PNG de fotografía pesa 10 veces lo que el JPEG equivalente y no gana
    # nada a cambio (medido: 3,5 MB contra 270 KB en una foto de celular).
    # Solo se conserva PNG si la imagen usa transparencia de verdad.
    if formato == "PNG" and "A" not in imagen.getbands() and "transparency" not in imagen.info:
        formato, extension = "JPEG", ".jpg"

    # La cámara del celular guarda la foto siempre en horizontal y anota la
    # rotación en el EXIF; al reescribirla ese dato se pierde y la foto sale
    # acostada, así que hay que aplicarlo antes.
    imagen = ImageOps.exif_transpose(imagen)
    imagen.thumbnail((lado, lado))
    if formato == "JPEG" and imagen.mode not in ("RGB", "L"):
        imagen = imagen.convert("RGB")

    buffer = io.BytesIO()
    opciones = {"optimize": True}
    if formato == "JPEG":
        opciones |= {"quality": 85, "progressive": True}
    imagen.save(buffer, format=formato, **opciones)
    # Solo el nombre del archivo: la ruta con fecha la vuelve a armar
    # `upload_to` al guardar.
    return ContentFile(buffer.getvalue(), name=f"{nombre}{extension}")


class ImagenProducto(models.Model):
    MAX_POR_PRODUCTO = 3

    producto = models.ForeignKey(
        Producto, on_delete=models.CASCADE, related_name="imagenes",
        help_text="Producto al que pertenece esta imagen.",
    )
    imagen = models.ImageField(upload_to="productos/%Y/%m/", help_text="Archivo de imagen del producto (JPG o PNG).")
    alt = models.CharField(
        "texto alternativo", max_length=160, blank=True,
        help_text="Para lectores de pantalla y cuando la imagen no carga.",
    )
    es_principal = models.BooleanField(
        default=False,
        help_text="Solo puede haber una imagen principal por producto; es la primera que se ve en el catálogo.",
    )
    orden = models.PositiveSmallIntegerField(default=0, help_text="Controla el orden de esta imagen dentro de la galería.")

    class Meta:
        verbose_name = "imagen de producto"
        verbose_name_plural = "imágenes de producto"
        ordering = ["producto", "-es_principal", "orden"]
        constraints = [
            models.UniqueConstraint(
                fields=["producto"],
                condition=models.Q(es_principal=True),
                name="una_imagen_principal_por_producto",
            ),
        ]

    def __str__(self):
        return f"{self.producto} · imagen {self.pk}"

    def clean(self):
        # El tope de 3 fotos por producto vive acá y no en cada formulario:
        # tanto el panel de gestión como la cuenta del proveedor cargan
        # imágenes, y los dos pasan por esta validación.
        if not self.producto_id:
            return
        otras = ImagenProducto.objects.filter(producto_id=self.producto_id).exclude(pk=self.pk).count()
        if otras >= self.MAX_POR_PRODUCTO:
            raise ValidationError(
                f"Este producto ya tiene {self.MAX_POR_PRODUCTO} fotos, que es el máximo. "
                "Borrá una para subir otra."
            )

    def save(self, *args, **kw):
        # `_committed` es False solo cuando hay un archivo recién subido sin
        # escribir: así guardar cualquier otro campo (marcar la principal,
        # cambiar el orden) no vuelve a recomprimir una foto ya procesada.
        if self.imagen and not self.imagen._committed:
            reducida = reducir_imagen(self.imagen)
            if reducida is not None:
                self.imagen = reducida

        # Marcar una imagen como principal desplaza a la anterior en vez de
        # chocar con la restricción de unicidad — el staff no tiene que
        # acordarse de desmarcar la vieja a mano en dos pasos.
        if self.es_principal:
            ImagenProducto.objects.filter(
                producto_id=self.producto_id, es_principal=True,
            ).exclude(pk=self.pk).update(es_principal=False)
        super().save(*args, **kw)

    def validate_constraints(self, exclude=None):
        # El `ModelForm` del panel valida constraints ANTES de llamar a
        # `save()`, así que sin este override el desplazamiento de arriba
        # nunca llega a correr: la validación ve a la imagen principal
        # vieja todavía en la base y rechaza el formulario con un error de
        # nombre de constraint, ilegible para el staff. Esta es la única
        # constraint del modelo y la garantiza `save()`, así que se salta
        # acá — sigue existiendo en la base como red de seguridad para
        # cualquier escritura que no pase por `save()` (ej. `bulk_create`).
        pass


class EscalaPrecio(models.Model):
    producto = models.ForeignKey(
        Producto, on_delete=models.CASCADE, related_name="escalas_precio",
        help_text="Producto al que aplica esta escala de precio.",
    )
    volumen_minimo = models.PositiveIntegerField(help_text="Cantidad mínima desde la que aplica este precio.")
    precio_unitario = models.DecimalField(
        max_digits=14, decimal_places=2,
        help_text="Precio por unidad a partir de ese volumen, en la moneda del producto.",
    )

    class Meta:
        verbose_name = "escala de precio"
        verbose_name_plural = "escalas de precio"
        ordering = ["producto", "volumen_minimo"]
        constraints = [
            models.UniqueConstraint(
                fields=["producto", "volumen_minimo"], name="escala_volumen_unico_por_producto"
            ),
        ]

    def __str__(self):
        return f"desde {self.volumen_minimo}: {self.precio_unitario} {self.producto.moneda}"


class Vendedor(models.Model):
    """Vendedor independiente de la Red Comercial (documento de producto,
    sección 64). Recomienda proveedores Premium Plus y gana comisión sobre
    los requerimientos que llegan con su código de referencia."""

    class Estado(models.TextChoices):
        ACTIVO = "activo", "Activo"
        INACTIVO = "inactivo", "Inactivo"

    nombre = models.CharField(max_length=120)
    whatsapp = models.CharField(max_length=40, blank=True)
    email = models.EmailField(blank=True)
    zona = models.CharField(max_length=120, blank=True, help_text="Zona donde opera (ciudad o región).")
    especialidad = models.CharField(max_length=120, blank=True, help_text="Rubro en el que se especializa.")
    comision = models.DecimalField(
        "Comisión (%)", max_digits=5, decimal_places=2, default=0,
        help_text="Comisión por defecto. Se puede pisar por vinculación individual.",
    )
    estado = models.CharField(max_length=10, choices=Estado.choices, default=Estado.ACTIVO)
    codigo_referencia = models.SlugField(
        max_length=40, unique=True, blank=True,
        help_text="Código único para su link de referido (?ref=CÓDIGO). Se genera solo desde "
        "el nombre si lo dejás vacío.",
    )
    creado = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "vendedor"
        ordering = ["nombre"]

    def __str__(self):
        return self.nombre

    def save(self, *args, **kw):
        if not self.codigo_referencia:
            base = slugify(f"V-{self.nombre}")[:34].upper()
            codigo, sufijo = base, 1
            while Vendedor.objects.exclude(pk=self.pk).filter(codigo_referencia=codigo).exists():
                sufijo += 1
                codigo = f"{base}{sufijo}"
            self.codigo_referencia = codigo
        super().save(*args, **kw)


class VendedorProducto(models.Model):
    """La "vinculación" del documento (sección 65): qué productos de un
    proveedor Premium Plus puede representar cada vendedor, y con qué
    comisión. El buscador de productos al vincular ya viene limitado a
    proveedores con Premium Plus activo desde el formulario del panel
    (`panel/urls.py`, recurso "vinculacion") — acá no hace falta repetir esa
    validación porque Django ya rechaza cualquier producto fuera de esa
    queryset al validar el `ModelChoiceField`."""

    vendedor = models.ForeignKey(Vendedor, on_delete=models.CASCADE, related_name="vinculaciones")
    producto = models.ForeignKey(Producto, on_delete=models.CASCADE, related_name="vendedores")
    comision = models.DecimalField(
        "Comisión (%)", max_digits=5, decimal_places=2, null=True, blank=True,
        help_text="Dejalo vacío para usar la comisión por defecto del vendedor.",
    )
    vinculado_en = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "vinculación de vendedor"
        verbose_name_plural = "vinculaciones de vendedor"
        constraints = [
            models.UniqueConstraint(fields=["vendedor", "producto"], name="vinculacion_unica_por_producto"),
        ]

    def __str__(self):
        return f"{self.vendedor} · {self.producto}"

    def comision_efectiva(self):
        return self.comision if self.comision is not None else self.vendedor.comision


class Requerimiento(models.Model):
    """El "Enviar requerimiento" del mockup. Todavía no hay login de empresas
    compradoras en el sitio público, así que el contacto se pide en el propio
    formulario en vez de asumir una sesión (a diferencia del mockup)."""

    class Estado(models.TextChoices):
        NUEVO = "nuevo", "Nuevo"
        EN_REVISION = "en_revision", "En revisión"
        RESPONDIDO = "respondido", "Respondido"
        CERRADO = "cerrado", "Cerrado"

    class Origen(models.TextChoices):
        ORGANICO = "organico", "Orgánico"
        VENDEDOR = "vendedor", "Vendedor"

    producto = models.ForeignKey(
        Producto, on_delete=models.PROTECT, related_name="requerimientos",
        help_text="Producto sobre el que trata este requerimiento.",
    )
    origen = models.CharField(
        max_length=10, choices=Origen.choices, default=Origen.ORGANICO,
        help_text="Se completa solo si el visitante llegó con un link de referido "
        "(?ref=código, documento de producto, secciones 66-67). No lo pisa el comprador.",
    )
    vendedor = models.ForeignKey(
        Vendedor, on_delete=models.SET_NULL, null=True, blank=True, related_name="requerimientos",
        help_text="Vendedor cuyo código de referencia trajo este requerimiento (si el origen es «Vendedor»).",
    )

    nombre_contacto = models.CharField(max_length=120, help_text="Nombre de la persona que envió el requerimiento.")
    email_contacto = models.EmailField(help_text="Correo para responderle.")
    telefono_contacto = models.CharField(max_length=40, blank=True, help_text="Teléfono de contacto (opcional).")
    empresa_compradora = models.CharField(
        max_length=200, blank=True,
        help_text="Empresa que envía el requerimiento, tal como la escribió (texto libre, no vinculado a una Empresa registrada).",
    )

    volumen_requerido = models.CharField(max_length=120, blank=True, help_text="Volumen que pidió, en sus propias palabras.")
    plazo_esperado = models.CharField(max_length=120, blank=True, help_text="Plazo en que espera recibirlo, en sus propias palabras.")
    observaciones = models.TextField(blank=True, help_text="Cualquier detalle adicional que haya dejado.")

    estado = models.CharField(
        max_length=15, choices=Estado.choices, default=Estado.NUEVO,
        help_text="Estado interno de seguimiento: usalo para saber en qué etapa está este requerimiento.",
    )
    creado = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "requerimiento"
        ordering = ["-creado"]

    def __str__(self):
        return f"{self.producto} · {self.nombre_contacto}"


class Oportunidad(models.Model):
    """El pipeline de venta de un lead (documento de producto, sección 70).
    No se crea sola por cada requerimiento — el staff decide a mano cuáles
    leads pasan a seguimiento formal de oportunidad."""

    class Estado(models.TextChoices):
        NUEVA = "nueva", "Nueva"
        CONTACTADA = "contactada", "Contactada"
        EN_COTIZACION = "en_cotizacion", "En cotización"
        EN_NEGOCIACION = "en_negociacion", "En negociación"
        GANADA = "ganada", "Ganada"
        PERDIDA = "perdida", "Perdida"

    requerimiento = models.OneToOneField(
        Requerimiento, on_delete=models.CASCADE, related_name="oportunidad",
        help_text="El lead del que nace esta oportunidad.",
    )
    estado = models.CharField(max_length=15, choices=Estado.choices, default=Estado.NUEVA)
    creada = models.DateTimeField(auto_now_add=True)
    actualizada = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "oportunidad"
        ordering = ["-actualizada"]

    def __str__(self):
        return f"{self.requerimiento} · {self.get_estado_display()}"


class Venta(models.Model):
    """"Registrar venta concretada" (sección 71): tanto para una venta que se
    cerró offline como para dejar constancia de una que se originó acá.
    Al guardarse por primera vez calcula sola la comisión del vendedor
    (sección 72), si es que el lead vino atribuido a uno."""

    oportunidad = models.OneToOneField(
        Oportunidad, on_delete=models.CASCADE, related_name="venta",
        help_text="Tiene que ser una oportunidad en estado «Ganada».",
    )
    monto = models.DecimalField(max_digits=12, decimal_places=2)
    comprobante_externo = models.CharField(
        max_length=120, blank=True,
        help_text="Número de factura, boleta u otra referencia externa (opcional).",
    )
    fecha = models.DateField()
    observaciones = models.TextField(blank=True)
    creada = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "venta"
        ordering = ["-fecha"]

    def __str__(self):
        return f"{self.oportunidad.requerimiento.producto} · {self.monto}"

    def save(self, *args, **kw):
        es_nueva = self.pk is None
        super().save(*args, **kw)
        if es_nueva:
            self._crear_comision_si_corresponde()

    def _crear_comision_si_corresponde(self):
        vendedor = self.oportunidad.requerimiento.vendedor
        if not vendedor or hasattr(self, "comision"):
            return
        producto = self.oportunidad.requerimiento.producto
        vinculacion = VendedorProducto.objects.filter(vendedor=vendedor, producto=producto).first()
        porcentaje = vinculacion.comision_efectiva() if vinculacion else vendedor.comision
        Comision.objects.create(venta=self, porcentaje=porcentaje, monto=self.monto * porcentaje / 100)


class Comision(models.Model):
    """Documento de producto, sección 73: se calcula sola (`Venta.save()`),
    acá el staff solo avanza el «Estado» a medida que se confirma y se paga."""

    class Estado(models.TextChoices):
        PENDIENTE = "pendiente", "Pendiente"
        CONFIRMADA = "confirmada", "Confirmada"
        PAGADA = "pagada", "Pagada"

    venta = models.OneToOneField(Venta, on_delete=models.CASCADE, related_name="comision")
    porcentaje = models.DecimalField("Porcentaje (%)", max_digits=5, decimal_places=2)
    monto = models.DecimalField(
        max_digits=12, decimal_places=2, help_text="Monto de venta × porcentaje. Se calcula solo.",
    )
    estado = models.CharField(max_length=10, choices=Estado.choices, default=Estado.PENDIENTE)
    creada = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "comisión"
        verbose_name_plural = "comisiones"
        ordering = ["-creada"]

    def __str__(self):
        return f"{self.venta} · {self.monto}"

    def vendedor(self):
        return self.venta.oportunidad.requerimiento.vendedor

    def producto(self):
        return self.venta.oportunidad.requerimiento.producto

    def proveedor(self):
        return self.producto().empresa
