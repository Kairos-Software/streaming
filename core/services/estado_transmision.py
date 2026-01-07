from django.utils import timezone
from django.db import transaction
from django.conf import settings

from core.models import StreamConnection, CanalTransmision
from core.services.ffmpeg_manager import (
    start_program_stream,
    stop_program_stream,
)
from core.services.notificaciones_tiempo_real import (
    notificar_actualizacion_camara,
    notificar_camara_eliminada,
    notificar_estado_canal,
)


def detener_transmision_usuario(user):
    StreamConnection.objects.filter(
        user=user,
        status=StreamConnection.Status.ON_AIR,
    ).update(status=StreamConnection.Status.READY)

    stop_program_stream(user)

    canal, _ = CanalTransmision.objects.get_or_create(usuario=user)
    canal.en_vivo = False
    canal.inicio_transmision = None
    canal.url_hls = None
    canal.save(update_fields=["en_vivo", "inicio_transmision", "url_hls"])

    for conn in StreamConnection.objects.filter(user=user):
        notificar_actualizacion_camara(user, conn.cam_index)

    notificar_estado_canal(user)


def poner_camara_al_aire(user, cam_index):
    with transaction.atomic():
        camaras_previas = StreamConnection.objects.filter(
            user=user,
            status=StreamConnection.Status.ON_AIR,
        )

        indices_previos = [c.cam_index for c in camaras_previas]
        camaras_previas.update(status=StreamConnection.Status.READY)

        conn = StreamConnection.objects.filter(
            user=user,
            cam_index=cam_index,
            status=StreamConnection.Status.READY,
        ).first()

        if not conn:
            raise ValueError("Cámara no disponible o no autorizada")

        conn.status = StreamConnection.Status.ON_AIR
        conn.save(update_fields=["status"])

        for idx in indices_previos:
            notificar_actualizacion_camara(user, idx)

        notificar_actualizacion_camara(user, cam_index)

        # FFmpeg SOLO maneja el program
        stop_program_stream(user)
        start_program_stream(user=user, stream_key=conn.stream_key)

        canal, _ = CanalTransmision.objects.get_or_create(usuario=user)
        canal.en_vivo = True
        canal.inicio_transmision = timezone.now()
        canal.url_hls = f"{settings.HLS_BASE_URL}/program/{user.username}.m3u8"
        canal.save()

        notificar_estado_canal(user)


def cerrar_camara_usuario(user, cam_index):
    eliminado, _ = StreamConnection.objects.filter(
        user=user,
        cam_index=cam_index,
    ).delete()

    if eliminado > 0:
        notificar_camara_eliminada(user, cam_index)


def limpiar_conexiones_huerfanas(usuario=None, segundos_timeout=120):
    """
    Limpia cámaras que dejaron de enviar keepalive.
    Esto NO toca nginx ni ffmpeg.
    """
    limite = timezone.now() - timezone.timedelta(seconds=segundos_timeout)

    conexiones = StreamConnection.objects.filter(
        status__in=[
            StreamConnection.Status.PENDING,
            StreamConnection.Status.READY,
            StreamConnection.Status.ON_AIR,
        ],
        ultimo_contacto__lt=limite,
    )

    if usuario:
        conexiones = conexiones.filter(user=usuario)

    for c in conexiones:
        notificar_camara_eliminada(c.user, c.cam_index)

    cantidad = conexiones.count()
    conexiones.delete()
    return cantidad
