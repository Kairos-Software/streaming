from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from django.conf import settings
from core.models import StreamConnection, CanalTransmision

# ===============================
# URL HLS según estado
# ===============================
def hls_url_for_connection(conn):
    """
    Genera la URL de HLS según el estado de la conexión.
    READY -> live/<stream_key>.m3u8
    ON_AIR -> program/<username>.m3u8
    """
    if conn.status == StreamConnection.Status.READY:
        url = f"{settings.HLS_BASE_URL}/live/{conn.stream_key}.m3u8"
    elif conn.status == StreamConnection.Status.ON_AIR:
        url = f"{settings.HLS_BASE_URL}/program/{conn.user.username}.m3u8"
    else:
        url = None
    print(f"[DEBUG] HLS URL generada para {conn.stream_key} ({conn.status}): {url}")
    return url


# ===============================
# NOTIFICACIÓN ACTUALIZACIÓN DE CÁMARAS
# ===============================
def notificar_actualizacion_camara(user, cam_index=None):
    conexiones = StreamConnection.objects.filter(user=user)
    data = {}

    for c in conexiones:
        hls_url = hls_url_for_connection(c)

        if cam_index is None or c.cam_index == cam_index:
            data[str(c.cam_index)] = {
                "status": c.status,
                "authorized": c.authorized,
                "hls_url": hls_url,
            }

    if not data:
        print(f"[DEBUG] No hay datos de cámaras para notificar a {user.username}")
        return

    try:
        layer = get_channel_layer()
        async_to_sync(layer.group_send)(
            f"usuario_{user.id}",
            {
                "type": "estado_camaras",
                "cameras": data,
            },
        )
        print(f"[DEBUG] Notificación enviada a usuario {user.username}: {data}")
    except Exception as e:
        print(f"[ERROR] No se pudo notificar cámaras de {user.username}: {e}")


# ===============================
# NOTIFICACIÓN CAMARA ACTUALIZADA
# ===============================
def notificar_camara_actualizada(user, cam_index):
    try:
        c = StreamConnection.objects.get(user=user, cam_index=cam_index)
    except StreamConnection.DoesNotExist:
        print(f"[DEBUG] Cámara {cam_index} no existe para {user.username}")
        return

    hls_url = hls_url_for_connection(c)

    try:
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
        print(f"[DEBUG] Cámara {cam_index} actualizada enviada a {user.username}")
    except Exception as e:
        print(f"[ERROR] No se pudo notificar cámara {cam_index} de {user.username}: {e}")


# ===============================
# NOTIFICACIÓN CAMARA ELIMINADA
# ===============================
def notificar_camara_eliminada(user, cam_index):
    try:
        layer = get_channel_layer()
        async_to_sync(layer.group_send)(
            f"usuario_{user.id}",
            {
                "type": "camara_eliminada",
                "cam_index": cam_index,
            },
        )
        print(f"[DEBUG] Notificación cámara eliminada {cam_index} enviada a {user.username}")
    except Exception as e:
        print(f"[ERROR] No se pudo notificar eliminación de cámara {cam_index} de {user.username}: {e}")


# ===============================
# NOTIFICACIÓN ESTADO CANAL
# ===============================
def notificar_estado_canal(user):
    canal = CanalTransmision.objects.filter(usuario=user).first()
    try:
        layer = get_channel_layer()
        async_to_sync(layer.group_send)(
            f"usuario_{user.id}",
            {
                "type": "estado_canal",
                "en_vivo": canal.en_vivo if canal else False,
                "hls_url": canal.url_hls if canal else None,  # corregido
            },
        )
        print(f"[DEBUG] Notificación estado canal enviada a {user.username}")
    except Exception as e:
        print(f"[ERROR] No se pudo notificar estado canal de {user.username}: {e}")

