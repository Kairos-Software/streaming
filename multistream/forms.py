from django import forms
from multistream.models import CuentaYouTube


class CuentaYouTubeForm(forms.ModelForm):
    class Meta:
        model = CuentaYouTube
        fields = ['id_canal', 'nombre_canal', 'url_ingestion', 'clave_transmision', 'activo']
        widgets = {
            'id_canal': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'ID del canal'}),
            'nombre_canal': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Nombre del canal'}),
            'url_ingestion': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'rtmp://a.rtmp.youtube.com/live2'}),
            'clave_transmision': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'clave-de-ejemplo'}),
            'activo': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }
