from django.utils import timezone
from django.db import transaction
from django.conf import settings
from django.core.exceptions import ObjectDoesNotExist
import os
from core.models import StreamConnection, CanalTransmision
from core.services.ffmpeg_manager import start_program_stream, stop_program_stream, is_program_stream_running
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
    Detiene completamente la transmisión del usuario.

    REGLAS:
    - Es la ÚNICA función que apaga FFmpeg
    - Pasa todas las cámaras ON_AIR → READY
    - Marca el canal como OFFLINE
    """

    # ===============================
    # 1. BAJAR TODAS LAS CÁMARAS ON_AIR
    # ===============================
    camaras_on_air = StreamConnection.objects.filter(
        user=user,
        status=StreamConnection.Status.ON_AIR,
    )

    indices = list(camaras_on_air.values_list("cam_index", flat=True))

    if not indices:
        print(f"[DEBUG] detener_transmision_usuario: no hay cámaras ON_AIR para {user.username}")
        return

    camaras_on_air.update(status=StreamConnection.Status.READY)

    # ===============================
    # 2. DETENER FFMPEG (PROGRAM)
    # ===============================
    print(f"[DEBUG] Deteniendo program stream de {user.username}")
    stop_program_stream(user)

    # ===============================
    # 3. MARCAR CANAL COMO OFFLINE
    # ===============================
    canal, _ = CanalTransmision.objects.get_or_create(usuario=user)
    canal.en_vivo = False
    canal.inicio_transmision = None
    canal.url_hls = ""
    canal.save(update_fields=["en_vivo", "inicio_transmision", "url_hls"])

    # ===============================
    # 4. NOTIFICAR CÁMARAS AFECTADAS
    # ===============================
    for idx in indices:
        notificar_actualizacion_camara(user, idx)

    # ===============================
    # 5. NOTIFICAR ESTADO DEL CANAL
    # ===============================
    notificar_estado_canal(user)


# ===============================
# PONER UNA CÁMARA AL AIRE
# ===============================
def poner_camara_al_aire(user, cam_index):
    """
    Cambia la cámara activa (ON_AIR) del usuario.

    REGLAS IMPORTANTES:
    - Cambiar de cámara NO corta la transmisión
    - FFmpeg solo se inicia si no está corriendo
    - El canal está EN VIVO si hay una cámara ON_AIR
    """

    with transaction.atomic():

        # ===============================
        # 1. BAJAR CÁMARAS PREVIAS ON_AIR
        # ===============================
        camaras_previas = StreamConnection.objects.filter(
            user=user,
            status=StreamConnection.Status.ON_AIR,
        )

        indices_previos = list(
            camaras_previas.values_list("cam_index", flat=True)
        )

        camaras_previas.update(status=StreamConnection.Status.READY)

        # ===============================
        # 2. BUSCAR CÁMARA A ACTIVAR
        # ===============================
        conn = StreamConnection.objects.filter(
            user=user,
            cam_index=cam_index,
            status=StreamConnection.Status.READY,
        ).first()

        if not conn:
            raise ValueError(
                f"Cámara {cam_index} no disponible o no autorizada para {user.username}"
            )

        # ===============================
        # 3. MARCAR CÁMARA COMO ON_AIR
        # ===============================
        conn.status = StreamConnection.Status.ON_AIR
        conn.save(update_fields=["status"])

        # ===============================
        # 4. NOTIFICAR CÁMARAS PREVIAS
        # ===============================
        for idx in indices_previos:
            notificar_actualizacion_camara(user, idx)

        # ===============================
        # 5. NOTIFICAR CÁMARA ACTUAL
        # ===============================
        notificar_actualizacion_camara(user, cam_index)

        # ===============================
        # 6. INICIAR FFMPEG SOLO SI NO CORRE
        # ===============================
        if not is_program_stream_running(user):
            start_program_stream(user=user, stream_key=conn.stream_key)

        # ===============================
        # 7. MARCAR CANAL COMO EN VIVO
        # ===============================
        canal, _ = CanalTransmision.objects.get_or_create(usuario=user)

        canal.en_vivo = True
        canal.inicio_transmision = timezone.now()
        canal.url_hls = f"{settings.HLS_BASE_URL}/program/{user.username}.m3u8"

        canal.save(update_fields=[
            "en_vivo",
            "inicio_transmision",
            "url_hls",
        ])

        # ===============================
        # 8. NOTIFICAR ESTADO DEL CANAL
        # ===============================
        notificar_estado_canal(user)


# ===============================
# CERRAR UNA CÁMARA ESPECÍFICA
# ===============================
def cerrar_camara_usuario(user, cam_index):
    """
    Elimina una cámara específica.
    Si estaba ON_AIR, apaga la transmisión.
    """

    conn = StreamConnection.objects.filter(
        user=user,
        cam_index=cam_index,
    ).first()

    if not conn:
        return

    estaba_on_air = conn.status == StreamConnection.Status.ON_AIR

    conn.delete()
    notificar_camara_eliminada(user, cam_index)

    if estaba_on_air:
        print(f"[DEBUG] Se cerró cámara ON_AIR → apagando transmisión")
        detener_transmision_usuario(user)


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


def reconciliar_estado_canal(user):
    """
    Mantiene el estado del canal en función de las cámaras ON_AIR y el archivo HLS.
    """
    hay_on_air = StreamConnection.objects.filter(
        user=user,
        status=StreamConnection.Status.ON_AIR,
    ).exists()

    canal, _ = CanalTransmision.objects.get_or_create(usuario=user)

    ruta_m3u8 = os.path.join(
        r"D:\nginx-rtmp\nginx-rtmp-win32-dev\temp\hls\program",
        f"{user.username}.m3u8"
    )

    if hay_on_air and os.path.exists(ruta_m3u8):
        if not canal.en_vivo:
            canal.en_vivo = True
            canal.url_hls = f"{settings.HLS_BASE_URL}/program/{user.username}.m3u8"
            canal.inicio_transmision = timezone.now()
            canal.save(update_fields=["en_vivo", "url_hls", "inicio_transmision"])
            notificar_estado_canal(user)
    else:
        if canal.en_vivo:
            canal.en_vivo = False
            canal.inicio_transmision = None
            canal.url_hls = ""
            canal.save(update_fields=["en_vivo", "inicio_transmision", "url_hls"])
            notificar_estado_canal(user)


def notificar_estado_inicial_usuario(user):
    """
    Reenvía el estado real de todas las cámaras y del canal.
    Se usa cuando el usuario entra o refresca el panel.
    """
    conexiones = StreamConnection.objects.filter(user=user)

    for conn in conexiones:
        notificar_actualizacion_camara(user, conn.cam_index)

    notificar_estado_canal(user)
