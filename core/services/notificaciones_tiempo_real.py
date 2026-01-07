from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from django.conf import settings
from core.models import StreamConnection, CanalTransmision


def hls_live_url(stream_key):
    return f"{settings.HLS_BASE_URL}/hls/live/{stream_key}.m3u8"


def notificar_actualizacion_camara(user, cam_index=None):
    conexiones = StreamConnection.objects.filter(user=user)
    data = {}

    for c in conexiones:
        hls_url = None
        if c.status in [
            StreamConnection.Status.READY,
            StreamConnection.Status.ON_AIR,
        ]:
            hls_url = hls_live_url(c.stream_key)

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
            "cameras": data,
        },
    )


def notificar_camara_actualizada(user, cam_index):
    try:
        c = StreamConnection.objects.get(user=user, cam_index=cam_index)
    except StreamConnection.DoesNotExist:
        return

    hls_url = None
    if c.status in [
        StreamConnection.Status.READY,
        StreamConnection.Status.ON_AIR,
    ]:
        hls_url = hls_live_url(c.stream_key)

    layer = get_channel_layer()
    async_to_sync(layer.group_send)(
        f"usuario_{user.id}",
        {
            "type": "camara_actualizada",
            "cam_index": cam_index,
            "estado": c.status,
            "authorized": c.authorized,
            "hls_url": hls_url,
        },
    )


def notificar_camara_eliminada(user, cam_index):
    layer = get_channel_layer()
    async_to_sync(layer.group_send)(
        f"usuario_{user.id}",
        {
            "type": "camara_eliminada",
            "cam_index": cam_index,
        },
    )


def notificar_estado_canal(user):
    canal = CanalTransmision.objects.filter(usuario=user).first()

    layer = get_channel_layer()
    async_to_sync(layer.group_send)(
        f"usuario_{user.id}",
        {
            "type": "estado_canal",
            "en_vivo": canal.en_vivo if canal else False,
            "url_hls": canal.url_hls if canal else None,
        },
    )
