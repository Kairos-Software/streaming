from django.utils import timezone
from django.conf import settings
import os
from core.models import StreamConnection, CanalTransmision
from core.services.ffmpeg_manager import (
    start_program_hls,
    switch_program_camera,
    stop_program_hls,
)
from core.services.notificaciones_tiempo_real import (
    notificar_actualizacion_camara,
    notificar_camara_actualizada,
    notificar_camara_eliminada,
    notificar_estado_canal,
)
from core.services.limpieza_hls import limpiar_hls_usuario


# ===============================
# DETENER TODAS LAS TRANSMISIONES DE UN USUARIO
# ===============================
def detener_transmision_usuario(user):
    """
    FINAL REAL del evento.
    Se llama SOLO cuando el usuario aprieta 'Detener transmisión'.
    """

    print(f"[DEBUG] FINALIZANDO transmisión de {user.username}")

    # 1️⃣ Detener FFmpeg (HLS + feeder)
    stop_program_hls(user)

    # 1b. Detener feeder de radio si estaba activo
    from core.services.radio_manager import stop_radio_feeder
    stop_radio_feeder(user)

    # 2️⃣ Limpiar HLS del usuario
    limpiar_hls_usuario(user.username)

    # 3️⃣ Bajar todas las cámaras a READY
    camaras = StreamConnection.objects.filter(
        user=user,
        status=StreamConnection.Status.ON_AIR
    )

    indices = list(camaras.values_list("cam_index", flat=True))
    camaras.update(
        status=StreamConnection.Status.READY,
        authorized=False
    )

    for idx in indices:
        notificar_actualizacion_camara(user, idx)

    # 4️⃣ Apagar canal (y resetear modo_radio)
    canal, _ = CanalTransmision.objects.get_or_create(usuario=user)
    canal.en_vivo = False
    canal.inicio_transmision = None
    canal.url_hls = ""
    canal.modo_radio = False
    canal.save(update_fields=["en_vivo", "inicio_transmision", "url_hls", "modo_radio"])

    # 5️⃣ Notificar frontend
    notificar_estado_canal(user)

    print(f"[DEBUG] Transmisión FINALIZADA correctamente para {user.username}")


def poner_camara_al_aire(user, cam_index):
    """
    Pone una cámara al aire.
    
    CORREGIDO: Ahora notifica cuando las cámaras anteriores bajan de estado.
    """
    try:
        conn = StreamConnection.objects.get(
            user=user,
            cam_index=cam_index,
            status=StreamConnection.Status.READY,
            authorized=True,
        )
    except StreamConnection.DoesNotExist:
        raise ValueError("La cámara no está lista para salir al aire")

    # 🔴 PASO 1: Bajar TODAS las cámaras ON_AIR a READY
    # Obtenemos la lista ANTES de actualizar para poder notificar
    camaras_anteriores = list(
        StreamConnection.objects.filter(
            user=user,
            status=StreamConnection.Status.ON_AIR
        ).values_list('cam_index', flat=True)
    )
    
    # Actualizamos todas a READY
    StreamConnection.objects.filter(
        user=user,
        status=StreamConnection.Status.ON_AIR
    ).update(status=StreamConnection.Status.READY)
    
    # 🔔 Notificar cada cámara que bajó de estado
    for prev_cam_index in camaras_anteriores:
        print(f"[DEBUG] Bajando cámara {prev_cam_index} de ON_AIR a READY")
        notificar_camara_actualizada(user, prev_cam_index)

    # 🟢 PASO 2: Subir la nueva cámara a ON_AIR
    conn.status = StreamConnection.Status.ON_AIR
    conn.save()
    
    # 🔔 Notificar la nueva cámara ON_AIR
    print(f"[DEBUG] Subiendo cámara {cam_index} a ON_AIR")
    notificar_camara_actualizada(user, cam_index)

    # 🎬 PASO 3: Crear / actualizar canal
    canal, created = CanalTransmision.objects.get_or_create(
        usuario=user,
        defaults={
            "en_vivo": True,
            "inicio_transmision": timezone.now(),
        }
    )
    if not canal.en_vivo:
        canal.en_vivo = True
        canal.inicio_transmision = timezone.now()
        canal.save()

    # 🔄 PASO 4: Cambiar fuente de video
    # Primero feeder
    switch_program_camera(user, conn.stream_key)

    # 🔥 Después maestro
    start_program_hls(user)


# ===============================
# CERRAR UNA CÁMARA ESPECÍFICA
# ===============================
def cerrar_camara_usuario(user, cam_index):
    """
    Elimina una cámara específica.
    No apaga la transmisión aquí: la detención global se decide
    fuera (p.ej., en stream_finalizado) para evitar cortar durante un switch.
    """
    conn = StreamConnection.objects.filter(
        user=user,
        cam_index=cam_index,
    ).first()

    if not conn:
        return

    conn.delete()
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


def reconciliar_estado_canal(user):
    """
    El canal SOLO se apaga si la transmisión fue finalizada explícitamente.
    Los cambios de cámara NO afectan el estado del canal.
    """

    canal, _ = CanalTransmision.objects.get_or_create(usuario=user)

    ruta_m3u8 = os.path.join(
        settings.HLS_PATH,
        "program",
        f"{user.username}.m3u8"
    )

    # Si ffmpeg está activo y existe el HLS → canal en vivo
    hls_existe = os.path.exists(ruta_m3u8)

    if hls_existe:
        if not canal.en_vivo:
            canal.en_vivo = True
            canal.url_hls = f"{settings.HLS_BASE_URL}/program/{user.username}.m3u8"
            canal.inicio_transmision = timezone.now()
            canal.save(update_fields=["en_vivo", "url_hls", "inicio_transmision"])
            notificar_estado_canal(user)
    else:
        if canal.en_vivo:
            canal.en_vivo = False
            canal.url_hls = ""
            canal.inicio_transmision = None
            canal.save(update_fields=["en_vivo", "url_hls", "inicio_transmision"])
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


def iniciar_transmision_usuario(user):
    """
    INICIO REAL del evento.
    Se llama UNA sola vez, cuando pasa la primera cámara a ON_AIR.
    """

    canal, _ = CanalTransmision.objects.get_or_create(usuario=user)

    if canal.en_vivo:
        return  # ya está en vivo, no reiniciar nada

    print(f"[DEBUG] INICIANDO transmisión de {user.username}")

    start_program_hls(user)

    canal.en_vivo = True
    canal.inicio_transmision = timezone.now()
    canal.url_hls = f"{settings.HLS_BASE_URL}/program/{user.username}.m3u8"
    canal.save(update_fields=["en_vivo", "inicio_transmision", "url_hls"])

    notificar_estado_canal(user)