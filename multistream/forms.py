from django import forms
from multistream.models import CuentaYouTube, CuentaFacebook


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


class CuentaFacebookForm(forms.ModelForm):
    class Meta:
        model = CuentaFacebook
        fields = ['id_pagina', 'nombre_pagina', 'url_ingestion', 'clave_transmision', 'activo']
        widgets = {
            'id_pagina': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'ID de la página'}),
            'nombre_pagina': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Nombre de la página'}),
            'url_ingestion': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'rtmps://live-api-s.facebook.com:443/rtmp/'}),
            'clave_transmision': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'clave-de-ejemplo'}),
            'activo': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }