# core/services/estado_transmision.py
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
    """
    Detiene la transmisión activa del usuario, apaga FFmpeg 
    y avisa por WebSocket.
    """
    # 1. Cambiar estado en DB
    StreamConnection.objects.filter(
        user=user,
        status=StreamConnection.Status.ON_AIR
    ).update(status=StreamConnection.Status.READY)

    # 2. Detener FFmpeg
    stop_program_stream(user)

    # 3. Actualizar Canal
    canal, _ = CanalTransmision.objects.get_or_create(usuario=user)
    canal.en_vivo = False
    canal.inicio_transmision = None
    canal.save(update_fields=["en_vivo", "inicio_transmision"])

    # 4. Notificar a todas las cámaras (para que cambien de color en el front)
    for conn in StreamConnection.objects.filter(user=user):
        notificar_actualizacion_camara(user, conn.cam_index)

    # 5. Notificar que el canal se apagó
    notificar_estado_canal(user)


def poner_camara_al_aire(user, cam_index):
    """
    Pone una cámara al aire, gestiona la concurrencia (baja las otras)
    y arranca FFmpeg.
    """
    with transaction.atomic():
        # 1. Bajar cualquier otra cámara que esté al aire
        camaras_previas = StreamConnection.objects.filter(
            user=user,
            status=StreamConnection.Status.ON_AIR,
        )
        
        # Guardamos los IDs para notificar luego
        indices_a_notificar = [c.cam_index for c in camaras_previas]
        
        camaras_previas.update(status=StreamConnection.Status.READY)

        # 2. Subir la cámara seleccionada
        conn = StreamConnection.objects.filter(
            user=user,
            cam_index=cam_index,
            status=StreamConnection.Status.READY,
        ).first()

        if not conn:
            raise ValueError("Cámara no disponible o no autorizada")

        conn.status = StreamConnection.Status.ON_AIR
        conn.save(update_fields=["status"])

        # 3. Notificaciones WebSocket
        # Avisamos a las que bajamos
        for idx in indices_a_notificar:
            notificar_actualizacion_camara(user, idx)
        # Avisamos a la que subimos
        notificar_actualizacion_camara(user, cam_index)

        # 4. Gestión de FFmpeg
        stop_program_stream(user)
        start_program_stream(user=user, stream_key=conn.stream_key)

        # 5. Actualizar estado del Canal
        canal, _ = CanalTransmision.objects.get_or_create(usuario=user)
        canal.en_vivo = True
        canal.inicio_transmision = timezone.now()
        canal.url_hls = f"{settings.HLS_BASE_URL}/hls/program/{user.username}.m3u8"
        canal.save()

        notificar_estado_canal(user)


def cerrar_camara_usuario(user, cam_index):
    """
    Elimina una cámara y notifica.
    """
    eliminado, _ = StreamConnection.objects.filter(
        user=user,
        cam_index=cam_index
    ).delete()

    if eliminado > 0:
        notificar_camara_eliminada(user, cam_index)


def limpiar_conexiones_huerfanas(usuario=None, segundos_timeout=120):
    limite = timezone.now() - timezone.timedelta(seconds=segundos_timeout)

    # LA CLAVE: .exclude(status=StreamConnection.Status.ON_AIR)
    # Esto evita que borremos la cámara que está transmitiendo
    conexiones = StreamConnection.objects.filter(
        status__in=[
            StreamConnection.Status.PENDING,
            StreamConnection.Status.READY,
            # Quitamos ON_AIR de la lista de candidatos a borrar por tiempo
        ],
        ultimo_contacto__lt=limite
    ).exclude(status=StreamConnection.Status.ON_AIR)

    if usuario:
        conexiones = conexiones.filter(user=usuario)

    # Notificar antes de borrar
    for c in conexiones:
        notificar_camara_eliminada(c.user, c.cam_index)

    cantidad = conexiones.count()
    conexiones.delete()
    return cantidad