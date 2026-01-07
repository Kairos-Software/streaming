from django.utils import timezone
from django.db import transaction
from django.conf import settings
from django.core.exceptions import ObjectDoesNotExist

from core.models import StreamConnection, CanalTransmision
from core.services.ffmpeg_manager import start_program_stream, stop_program_stream
from core.services.notificaciones_tiempo_real import (
    notificar_actualizacion_camara,
    notificar_camara_eliminada,
    notificar_estado_canal,
)


# ===============================
# DETENER TODAS LAS TRANSMISIONES DE UN USUARIO
# ===============================
def detener_transmision_usuario(user):
    """
    Pone todas las cámaras ON_AIR del usuario en READY,
    detiene el program stream y actualiza el canal y notificaciones.
    """
    # Cambia estado de cámaras
    StreamConnection.objects.filter(
        user=user,
        status=StreamConnection.Status.ON_AIR,
    ).update(status=StreamConnection.Status.READY)

    # Detener FFMPEG / program stream
    print(f"[DEBUG] Deteniendo program stream de {user.username}")
    stop_program_stream(user)

    # Actualiza canal principal
    canal, _ = CanalTransmision.objects.get_or_create(usuario=user)
    canal.en_vivo = False
    canal.inicio_transmision = None
    canal.url_hls = None
    canal.save(update_fields=["en_vivo", "inicio_transmision", "url_hls"])

    # Notificaciones
    for conn in StreamConnection.objects.filter(user=user):
        print(f"[DEBUG] Notificando cámara {conn.cam_index} de usuario {user.username}")
        notificar_actualizacion_camara(user, conn.cam_index)

    notificar_estado_canal(user)


# ===============================
# PONER UNA CÁMARA AL AIRE
# ===============================
def poner_camara_al_aire(user, cam_index):
    """
    Cambia el estado de la cámara a ON_AIR, detiene el program anterior,
    inicia FFMPEG para esta cámara y notifica al frontend.
    """
    with transaction.atomic():
        # Cualquier cámara previa ON_AIR se pone en READY
        camaras_previas = StreamConnection.objects.filter(
            user=user,
            status=StreamConnection.Status.ON_AIR,
        )
        indices_previos = [c.cam_index for c in camaras_previas]
        camaras_previas.update(status=StreamConnection.Status.READY)

        # Buscamos la cámara que queremos levantar
        conn = StreamConnection.objects.filter(
            user=user,
            cam_index=cam_index,
            status=StreamConnection.Status.READY,
        ).first()

        if not conn:
            raise ValueError(f"Cámara {cam_index} no disponible o no autorizada para {user.username}")

        # Cambiamos el estado a ON_AIR
        conn.status = StreamConnection.Status.ON_AIR
        conn.save(update_fields=["status"])

        # Notificaciones de cámaras previas
        for idx in indices_previos:
            print(f"[DEBUG] Notificando cámara previa {idx} de {user.username}")
            notificar_actualizacion_camara(user, idx)

        # Notificación de la cámara que se pone al aire
        print(f"[DEBUG] Notificando cámara {cam_index} ON_AIR para {user.username}")
        notificar_actualizacion_camara(user, cam_index)

        # FFMPEG: detiene program previo y lanza nuevo
        print(f"[DEBUG] Deteniendo program stream previo de {user.username}")
        stop_program_stream(user)
        print(f"[DEBUG] Iniciando program stream de {user.username} con clave {conn.stream_key}")
        start_program_stream(user=user, stream_key=conn.stream_key)

        # Actualizamos canal principal (usar solo el username)
        canal, _ = CanalTransmision.objects.get_or_create(usuario=user)
        canal.en_vivo = True
        canal.inicio_transmision = timezone.now()
        canal.url_hls = f"{settings.HLS_BASE_URL}/program/{user.username}.m3u8"
        canal.save(update_fields=["en_vivo", "inicio_transmision", "url_hls"])

        # Notificación de estado general del canal
        notificar_estado_canal(user)


# ===============================
# CERRAR UNA CÁMARA ESPECÍFICA
# ===============================
def cerrar_camara_usuario(user, cam_index):
    """
    Elimina la cámara y notifica al frontend
    """
    eliminado, _ = StreamConnection.objects.filter(
        user=user,
        cam_index=cam_index,
    ).delete()

    if eliminado > 0:
        print(f"[DEBUG] Cámara {cam_index} de {user.username} eliminada")
        notificar_camara_eliminada(user, cam_index)


# ===============================
# LIMPIAR CONEXIONES HUERFANAS
# ===============================
def limpiar_conexiones_huerfanas(usuario=None, segundos_timeout=120):
    """
    Limpia cámaras que dejaron de enviar keepalive.
    No toca nginx ni ffmpeg.
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
        print(f"[DEBUG] Eliminando conexión huérfana: {c.user.username} cam{c.cam_index}")
        notificar_camara_eliminada(c.user, c.cam_index)

    cantidad = conexiones.count()
    conexiones.delete()
    print(f"[DEBUG] Total conexiones huérfanas eliminadas: {cantidad}")
    return cantidad
