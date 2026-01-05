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



class ProfileSettingsForm(forms.ModelForm):

    username = forms.CharField(label="Nombre de usuario", max_length=150, widget=forms.TextInput(attrs={'class': 'settings-input'}))
    email = forms.EmailField(label="Correo Electrónico", widget=forms.EmailInput(attrs={'class': 'settings-input'}))

    class Meta:
        model = Cliente
        fields = ['bio', 'instagram', 'x_twitter', 'facebook', 'youtube', 'discord', 'tiktok']
        widgets = {
            'bio': forms.Textarea(attrs={'class': 'settings-input', 'rows': 4}),
            'instagram': forms.TextInput(attrs={'class': 'settings-input', 'placeholder': 'https://instagram.com/...'}),
            'x_twitter': forms.TextInput(attrs={'class': 'settings-input', 'placeholder': 'Handle de X'}),
            'facebook': forms.TextInput(attrs={'class': 'settings-input', 'placeholder': 'Link de Facebook'}),
            'youtube': forms.TextInput(attrs={'class': 'settings-input', 'placeholder': 'Link de YouTube'}),
            'discord': forms.TextInput(attrs={'class': 'settings-input', 'placeholder': 'Link de Discord'}),
            'tiktok': forms.TextInput(attrs={'class': 'settings-input', 'placeholder': 'Link de TikTok'}),
        }
        # Etiquetas opcionales para que se vea mejor en español
        labels = {
            'bio': 'Biografía',
            'x_twitter': 'X (Twitter)',
        }

    def __init__(self, *args, **kwargs):
        self.user_instance = kwargs.pop('user_instance', None)
        super(ProfileSettingsForm, self).__init__(*args, **kwargs)
        if self.user_instance:
            self.fields['username'].initial = self.user_instance.username
            self.fields['email'].initial = self.user_instance.email

    def clean_username(self):
        username = self.cleaned_data.get('username')
        # Importamos User aquí dentro para evitar problemas de importación circular si fuera necesario, 
        # pero como ya lo debes tener arriba, usa el global.
        # Asegúrate de tener: from django.contrib.auth.models import User al inicio del archivo
        if User.objects.filter(username=username).exclude(pk=self.user_instance.pk).exists():
            raise forms.ValidationError("Este nombre de usuario ya está en uso.")
        return username

    def save(self, commit=True):
        cliente = super(ProfileSettingsForm, self).save(commit=False)
        if self.user_instance:
            self.user_instance.username = self.cleaned_data['username']
            self.user_instance.email = self.cleaned_data['email']
            if commit:
                self.user_instance.save()
                cliente.save()
        return cliente
        
# --- FORMULARIO DE PREFERENCIAS ---
class PreferenciasForm(forms.ModelForm):
    class Meta:
        model = Cliente
        fields = ['pref_autoplay', 'pref_modo_teatro', 'pref_emails']

# --- FORMULARIO DE NOTIFICACIONES ---
class NotificacionesForm(forms.ModelForm):
    class Meta:
        model = Cliente
        fields = ['notif_live', 'notif_chat_mentions', 'notif_marketing']