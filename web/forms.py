from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User
from django.forms import inlineformset_factory

from catalogo.models import (
    Ciudad,
    Empresa,
    ImagenProducto,
    Pais,
    Producto,
    Region,
    Requerimiento,
)


class RequerimientoForm(forms.ModelForm):
    class Meta:
        model = Requerimiento
        fields = [
            "nombre_contacto", "email_contacto", "telefono_contacto", "empresa_compradora",
            "volumen_requerido", "plazo_esperado", "observaciones",
        ]
        widgets = {
            "volumen_requerido": forms.TextInput(attrs={"placeholder": "Ej. 3 pallets / mes"}),
            "plazo_esperado": forms.TextInput(attrs={"placeholder": "Ej. Dentro de 30 días"}),
            "observaciones": forms.Textarea(
                attrs={"rows": 3, "placeholder": "Etiquetado, certificaciones, condiciones de pago…"}
            ),
        }


class RegistroProveedorForm(UserCreationForm):
    """"Regístra tu empresa" (documento de membresías, sección 32): crea la
    cuenta y la empresa en un solo paso. Arranca siempre en plan Free y sin
    verificar — nada de eso se autodeclara ni se auto-otorga acá."""

    razon_social = forms.CharField(max_length=200, label="Razón social")
    nombre_comercial = forms.CharField(max_length=200, required=False, label="Nombre comercial")
    identificador_tributario = forms.CharField(max_length=32, label="RUT / NIT")
    pais = forms.ModelChoiceField(queryset=Pais.objects.all(), label="País")
    region = forms.ModelChoiceField(queryset=Region.objects.all(), label="Región")
    ciudad = forms.ModelChoiceField(queryset=Ciudad.objects.all(), label="Ciudad")

    class Meta(UserCreationForm.Meta):
        model = User
        fields = ("username", "email")

    def clean_email(self):
        email = self.cleaned_data["email"]
        if email and User.objects.filter(email=email).exists():
            raise forms.ValidationError("Ya hay una cuenta registrada con ese email.")
        return email


class MiEmpresaForm(forms.ModelForm):
    """Lo que el proveedor puede tocar de su propio perfil — nada de
    verificación, calificación o nivel comercial: eso lo decide MERCANTE365
    desde el panel, nunca la propia empresa."""

    class Meta:
        model = Empresa
        fields = [
            "razon_social", "nombre_comercial", "descripcion", "logo",
            "pais", "region", "ciudad", "direccion_fisica",
        ]


class MiProductoForm(forms.ModelForm):
    """Igual que el form del panel admin, pero sin los campos que decide
    MERCANTE365 (verificación, destacado) — el proveedor no se autodeclara
    verificado ni se autodestaca."""

    class Meta:
        model = Producto
        fields = [
            "categoria", "nombre", "slug", "sku", "descripcion_tecnica",
            "precio_unitario", "moneda", "cantidad_minima_pedido", "unidad_empaque",
            "plazo_entrega_dias", "stock_disponible", "atributos", "publicado",
        ]


# Las 3 fotos por producto de la cuenta del proveedor. `max_num` +
# `validate_max` es el tope de Django; el mismo tope vive además en
# `ImagenProducto.clean()` para que también aplique al panel de gestión.
# El proveedor no elige cuál es la principal: si no hay ninguna marcada,
# `Producto.imagen_principal` cae en la primera.
FotosProductoFormSet = inlineformset_factory(
    Producto, ImagenProducto,
    fields=["imagen", "alt"],
    widgets={"alt": forms.TextInput(attrs={"placeholder": "Qué se ve en la foto (opcional)"})},
    extra=ImagenProducto.MAX_POR_PRODUCTO,
    max_num=ImagenProducto.MAX_POR_PRODUCTO,
    validate_max=True,
    can_delete=True,
    can_delete_extra=False,  # el check «borrar» solo en las fotos que ya existen
)
