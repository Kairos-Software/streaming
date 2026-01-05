from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from core.models import StreamConnection, CanalTransmision

# ============================
# CONFIGURACIÓN VPS / HLS
# ============================
HLS_HOST = "kaircampanel.grupokairosarg.com"
HLS_PORT = "8080"


# ============================
# FUNCIONES DE NOTIFICACIÓN WS
# ============================

def notificar_actualizacion_camara(user, cam_index=None):
    """
    Envía el estado de las cámaras de un usuario.
    Si cam_index es None, envía todas las cámaras.
    """
    conexiones = StreamConnection.objects.filter(user=user)
    data = {}

    for c in conexiones:
        hls_url = None
        if c.status in [StreamConnection.Status.READY, StreamConnection.Status.ON_AIR]:
            hls_url = f"http://{HLS_HOST}:{HLS_PORT}/hls/live/{c.stream_key}.m3u8"

        if cam_index is None or c.cam_index == cam_index:
            data[str(c.cam_index)] = {
                "status": c.status,
                "authorized": c.authorized,
                "hls_url": hls_url,
            }

    if not data:
        return

    layer = get_channel_layer()
    async_to_sync(layer.group_send)(
        f"usuario_{user.id}",
        {
            "type": "estado_camaras",
            "cameras": data
        }
    )


def notificar_camara_actualizada(user, cam_index):
    """
    Envía un evento individual cuando cambia el estado de una cámara
    (pending, ready, on_air).
    """
    try:
        c = StreamConnection.objects.get(user=user, cam_index=cam_index)
    except StreamConnection.DoesNotExist:
        return

    hls_url = None
    if c.status in [StreamConnection.Status.READY, StreamConnection.Status.ON_AIR]:
        hls_url = f"http://{HLS_HOST}:{HLS_PORT}/hls/live/{c.stream_key}.m3u8"

    layer = get_channel_layer()
    async_to_sync(layer.group_send)(
        f"usuario_{user.id}",
        {
            "type": "camara_actualizada",
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
    Envía el estado del canal del usuario (en vivo o no) y la URL HLS del canal.
    """
    canal = CanalTransmision.objects.filter(usuario=user).first()
    layer = get_channel_layer()
    async_to_sync(layer.group_send)(
        f"usuario_{user.id}",
        {
            "type": "estado_canal",
            "en_vivo": canal.en_vivo if canal else False,
            "url_hls": f"http://{HLS_HOST}:{HLS_PORT}/hls/program/{user.username}.m3u8" if canal else None,
        }
    )
