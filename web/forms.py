from django import forms

from catalogo.models import Requerimiento


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
