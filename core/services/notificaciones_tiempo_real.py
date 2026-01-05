from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from django.conf import settings
from core.models import StreamConnection, CanalTransmision

# ============================
# FUNCIONES DE NOTIFICACIÓN WS
# ============================


def notificar_estado_completo_camaras(user):
    """
    Envía el estado COMPLETO de TODAS las cámaras de un usuario.
    Usar solo en snapshot inicial o cuando se necesite refrescar todo.
    """
    conexiones = StreamConnection.objects.filter(user=user)
    data = {}

    for c in conexiones:
        hls_url = None
        if c.status in [StreamConnection.Status.READY, StreamConnection.Status.ON_AIR]:
            hls_url = f"{settings.HLS_BASE_URL}/hls/live/{c.stream_key}.m3u8"

        data[str(c.cam_index)] = {
            "status": c.status,
            "authorized": c.authorized,
            "hls_url": hls_url,
        }

    layer = get_channel_layer()
    async_to_sync(layer.group_send)(
        f"usuario_{user.id}",
        {
            "type": "estado_camaras",
            "cameras": data
        }
    )


def notificar_actualizacion_camara(user, cam_index):
    """
    Envía un evento individual cuando cambia el estado de UNA cámara específica.
    Este es más eficiente que enviar todo el estado.
    """
    try:
        c = StreamConnection.objects.get(user=user, cam_index=cam_index)
    except StreamConnection.DoesNotExist:
        return

    hls_url = None
    if c.status in [StreamConnection.Status.READY, StreamConnection.Status.ON_AIR]:
        hls_url = f"{settings.HLS_BASE_URL}/hls/live/{c.stream_key}.m3u8"

    layer = get_channel_layer()
    async_to_sync(layer.group_send)(
        f"usuario_{user.id}",
        {
            "type": "camara_actualizada",  # ← CRÍTICO: debe ser camara_actualizada
            "cam_index": cam_index,
            "estado": c.status,
            "authorized": c.authorized,
            "hls_url": hls_url,
        }
    )


def notificar_camara_eliminada(user, cam_index):
    """
    Envía un evento cuando se elimina una cámara.
    """
    layer = get_channel_layer()
    async_to_sync(layer.group_send)(
        f"usuario_{user.id}",
        {
            "type": "camara_eliminada",
            "cam_index": cam_index
        }
    )


def notificar_estado_canal(user):
    """
    Envía el estado del canal del usuario (en vivo o no).
    INCLUYE el HLS URL del programa completo.
    """
    try:
        canal = CanalTransmision.objects.get(usuario=user)
        en_vivo = canal.en_vivo
        hls_url = canal.url_hls if canal.en_vivo else None
    except CanalTransmision.DoesNotExist:
        en_vivo = False
        hls_url = None

    layer = get_channel_layer()
    async_to_sync(layer.group_send)(
        f"usuario_{user.id}",
        {
            "type": "estado_canal",
            "en_vivo": en_vivo,
            "hls_url": hls_url,  # ← CRÍTICO: debe incluir el URL del programa
        }
    )