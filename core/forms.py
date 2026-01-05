# core/forms.py
from django import forms
from django.contrib.auth.models import User
from .models import Cliente


class ClienteForm(forms.ModelForm):
    username = forms.CharField(max_length=150, label="Nombre de usuario")
    email = forms.EmailField(label="Email")
    password = forms.CharField(widget=forms.PasswordInput, label="Contraseña", required=False)

    class Meta:
        model = Cliente
        fields = ["nombre", "apellido", "dni", "telefono", "direccion"]

    def __init__(self, *args, **kwargs):
        # Si viene un cliente existente, precargar datos de su User
        super().__init__(*args, **kwargs)
        if self.instance and hasattr(self.instance, "user"):
            self.fields["username"].initial = self.instance.user.username
            self.fields["email"].initial = self.instance.user.email

    def save(self, commit=True):
        cliente = super().save(commit=False)
        if not hasattr(cliente, "user"):
            # Crear usuario nuevo si no existe
            user = User.objects.create_user(
                username=self.cleaned_data["username"],
                email=self.cleaned_data["email"],
                password=self.cleaned_data["password"]
            )
            cliente.user = user
        else:
            # Actualizar usuario existente
            user = cliente.user
            user.username = self.cleaned_data["username"]
            user.email = self.cleaned_data["email"]
            if self.cleaned_data["password"]:
                user.set_password(self.cleaned_data["password"])
            user.save()

        if commit:
            cliente.save()
        return cliente


class PinForm(forms.ModelForm):
    # Ocultamos el campo 'pin' del modelo y lo definimos
    # explícitamente como PasswordInput para mayor seguridad visual
    pin = forms.CharField(
        label='PIN Actual / Nuevo',
        max_length=10,
        min_length=4,  # Recomendable para un PIN
        widget=forms.PasswordInput(attrs={'placeholder': 'Introduce tu PIN'}),
        help_text="El PIN debe tener entre 4 y 10 caracteres."
    )
    
    class Meta:
        model = Cliente
        fields = ['pin']
        
    def clean_pin(self):
        # Puedes añadir validaciones adicionales aquí si es necesario
        pin = self.cleaned_data.get('pin')
        # Por ejemplo, asegurarse de que no son solo números repetidos, etc.
        return pin