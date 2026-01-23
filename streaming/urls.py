from django.contrib import admin
from django.urls import path, include  # ← Asegúrate de tener 'include'

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', include('core.urls')),  # ← Ya debes tener esto
    path('multistream/', include('multistream.urls')),  # ← AGREGAR ESTA LÍNEA
]
