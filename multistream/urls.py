from django.urls import path
from multistream.views import (
    ajustes_retransmision,
    iniciar_retransmision,
    detener_retransmision,
    estado_retransmisiones
)

urlpatterns = [
    # Configuración
    path("configuracion/retransmision/", ajustes_retransmision, name="ajustes_retransmision"),
    
    # API endpoints
    path("api/restream/start/", iniciar_retransmision, name="api_iniciar_retransmision"),
    path("api/restream/stop/<str:platform>/", detener_retransmision, name="api_detener_retransmision"),
    path("api/restream/status/", estado_retransmisiones, name="api_estado_retransmisiones"),
]