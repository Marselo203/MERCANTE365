"""
catalogo/models.py — modelos del catálogo B2B.

El contrato exacto (campos, choices, unicidades) sale de los dos seeds en
management/commands/. La herencia de atributos se resuelve caminando la cadena
de `padre`; no hay ruta materializada todavía.

Los `help_text` de los campos son los que se muestran como ayuda en cada
formulario del panel de gestión (ver panel/templates/panel/form.html) — es la
única fuente, no hay textos duplicados en las plantillas.
"""

from django.core.exceptions import ValidationError
from django.db import models


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
        PENDIENTE = "pendiente", "Pendiente"
        APROBADA = "aprobada", "Aprobada"
        RECHAZADA = "rechazada", "Rechazada"

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
        max_length=140, unique=True,
        help_text="Parte de la URL pública de la empresa. Minúsculas y guiones, sin espacios ni tildes.",
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

    estado_verificacion = models.CharField(
        max_length=12, choices=EstadoVerificacion.choices, default=EstadoVerificacion.PENDIENTE,
        help_text="Pasala a Aprobada recién cuando confirmaste sus datos. Mientras esté Pendiente no se muestra como verificada.",
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

    class Meta:
        verbose_name = "empresa"
        ordering = ["razon_social"]

    def __str__(self):
        return self.nombre_comercial or self.razon_social

    def progreso_checklist(self):
        total = len(self.CHECKLIST_CALIFICACION)
        hechos = sum(1 for campo in self.CHECKLIST_CALIFICACION if getattr(self, campo))
        return f"{hechos}/{total}"


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

    def con_descendientes(self):
        """IDs de esta categoría y de todas sus hijas, recursivo. Para filtrar
        productos por un rubro que puede tener subcategorías. Sin ruta
        materializada: alcanza mientras el árbol sea chico (ver seed_demo)."""
        ids = [self.pk]
        for hija in self.hijas.all():
            ids += hija.con_descendientes()
        return ids


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

    verificado = models.BooleanField(
        default=False,
        help_text="Marcalo cuando el equipo corroboró la información con el proveedor. "
        "Se muestra como insignia en el catálogo público.",
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
        return self.imagenes.filter(es_principal=True).first()

    def clean(self):
        """Valida `atributos` contra las definiciones heredadas de la categoría:
        rechaza claves no definidas, tipos equivocados, opciones fuera de lista
        y faltantes obligatorios."""
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


class ImagenProducto(models.Model):
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


class Requerimiento(models.Model):
    """El "Enviar requerimiento" del mockup. Todavía no hay login de empresas
    compradoras en el sitio público, así que el contacto se pide en el propio
    formulario en vez de asumir una sesión (a diferencia del mockup)."""

    class Estado(models.TextChoices):
        NUEVO = "nuevo", "Nuevo"
        EN_REVISION = "en_revision", "En revisión"
        RESPONDIDO = "respondido", "Respondido"
        CERRADO = "cerrado", "Cerrado"

    producto = models.ForeignKey(
        Producto, on_delete=models.PROTECT, related_name="requerimientos",
        help_text="Producto sobre el que trata este requerimiento.",
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
