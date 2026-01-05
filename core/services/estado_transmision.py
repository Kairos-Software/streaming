"""
estado_transmision.py

Este módulo contiene la lógica de negocio relacionada al estado
de las transmisiones en vivo:
- qué cámara está al aire
- inicio y fin de transmisión
- sincronización con ffmpeg
- notificaciones en tiempo real (WebSockets)

⚠️ No contiene lógica HTTP ni acceso a request/response.
⚠️ Puede ser llamado desde views, tareas automáticas o tests.
"""

from django.utils import timezone
from django.db import transaction

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
    """
    Detiene la transmisión activa del usuario.
    """

    StreamConnection.objects.filter(
        user=user,
        status=StreamConnection.Status.ON_AIR
    ).update(status=StreamConnection.Status.READY)

    stop_program_stream(user)

    canal, _ = CanalTransmision.objects.get_or_create(usuario=user)
    canal.en_vivo = False
    canal.inicio_transmision = None
    canal.save(update_fields=["en_vivo", "inicio_transmision"])

    for conn in StreamConnection.objects.filter(user=user):
        notificar_actualizacion_camara(user, conn.cam_index)

    notificar_estado_canal(user)


def poner_camara_al_aire(user, cam_index):
    """
    Pone una cámara del usuario al aire.
    Garantiza que solo una cámara esté ON_AIR.
    """

    with transaction.atomic():

        # Bajamos cualquier otra cámara
        StreamConnection.objects.filter(
            user=user,
            status=StreamConnection.Status.ON_AIR,
        ).update(status=StreamConnection.Status.READY)

        for conn in StreamConnection.objects.filter(user=user):
            notificar_actualizacion_camara(user, conn.cam_index)

        conn = StreamConnection.objects.filter(
            user=user,
            cam_index=cam_index,
            status=StreamConnection.Status.READY,
        ).first()

        if not conn:
            raise ValueError("Cámara no disponible")

        conn.status = StreamConnection.Status.ON_AIR
        conn.save(update_fields=["status"])

        notificar_actualizacion_camara(user, cam_index)

        stop_program_stream(user)
        start_program_stream(
            user=user,
            stream_key=conn.stream_key
        )

        canal, _ = CanalTransmision.objects.get_or_create(usuario=user)
        canal.en_vivo = True
        canal.inicio_transmision = timezone.now()
        canal.url_hls = f"http://kaircampanel.grupokairosarg.com/hls/program/{user.username}.m3u8"
        canal.save()

        notificar_estado_canal(user)


def cerrar_camara_usuario(user, cam_index):
    """
    Elimina una cámara activa o pendiente del usuario.
    """

    eliminado = StreamConnection.objects.filter(
        user=user,
        cam_index=cam_index
    ).delete()

    if eliminado[0]:
        notificar_camara_eliminada(user, cam_index)


def limpiar_conexiones_huerfanas(usuario=None, segundos_timeout=15):
    """
    Elimina conexiones RTMP que quedaron colgadas.
    """

    limite = timezone.now() - timezone.timedelta(seconds=segundos_timeout)

    conexiones = StreamConnection.objects.filter(
        status__in=[
            StreamConnection.Status.PENDING,
            StreamConnection.Status.READY,
            StreamConnection.Status.ON_AIR,
        ],
        conectado_en__lt=limite
    )

    if usuario:
        conexiones = conexiones.filter(user=usuario)

    eliminadas = conexiones.count()
    conexiones.delete()
    return eliminadas
