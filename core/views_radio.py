"""
Vistas para Modo Radio.
No modifica views.py existente.
"""
import os
import time
import logging
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.contrib.auth.decorators import login_required
from django.conf import settings
from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer

from core.models import CanalTransmision, StreamConnection
from core.services.radio_manager import start_radio_feeder, stop_radio_feeder
from core.services.ffmpeg_manager import (
    switch_program_camera,
    PROGRAM_FEEDER_PROCESSES,
    stop_program_hls,
    start_program_hls,
)

logger = logging.getLogger(__name__)


def _notificar_modo_radio(user_id, modo_radio: bool):
    try:
        layer = get_channel_layer()
        async_to_sync(layer.group_send)(
            f"usuario_{user_id}",
            {
                "type": "modo_radio_cambio",
                "modo_radio": modo_radio,
            }
        )
    except Exception as e:
        logger.error(f"[RADIO] Error notificando WebSocket: {e}")


@login_required
@require_POST
def activar_modo_radio(request):
    user = request.user

    canal = CanalTransmision.objects.filter(usuario=user).first()
    if not canal or not canal.en_vivo:
        return JsonResponse({"ok": False, "error": "No hay transmisión activa"}, status=400)

    if canal.modo_radio:
        return JsonResponse({"ok": True, "modo": "radio", "ya_activo": True})

    camara_on_air = StreamConnection.objects.filter(
        user=user,
        status=StreamConnection.Status.ON_AIR
    ).first()

    if not camara_on_air:
        return JsonResponse(
            {"ok": False, "error": "No hay cámara al aire para tomar el audio"},
            status=400
        )

    # ── Refrescar canal desde DB para obtener imagen más reciente ──
    canal.refresh_from_db()
    imagen_path = canal.get_imagen_radio()
    if not imagen_path or not os.path.isfile(imagen_path):
        return JsonResponse(
            {"ok": False, "error": "No tenés imagen de radio configurada. Andá a Ajustes > Perfil para subirla."},
            status=400
        )

    # ── Matar feeder de cámara antes de publicar en program_switch ──
    feeder_proc = PROGRAM_FEEDER_PROCESSES.get(user.id)
    if feeder_proc and feeder_proc.poll() is None:
        logger.info(f"[RADIO] Terminando feeder de cámara antes de activar radio")
        try:
            feeder_proc.terminate()
            feeder_proc.wait(timeout=3)
        except Exception as e:
            logger.warning(f"[RADIO] Error terminando feeder de cámara: {e}")
        time.sleep(2)  # Dar tiempo a que nginx-rtmp libere el slot

    # ── Reiniciar HLS maestro para que tome el nuevo flujo (radio) ──
    logger.info(f"[RADIO] Reiniciando HLS maestro antes de activar modo radio")
    stop_program_hls(user)
    time.sleep(1)
    start_program_hls(user)

    try:
        start_radio_feeder(user, camara_on_air.stream_key)
        canal.activar_modo_radio()
        _notificar_modo_radio(user.id, modo_radio=True)
        logger.info(f"[RADIO] Modo radio ACTIVADO para {user.username}")
        return JsonResponse({"ok": True, "modo": "radio"})
    except Exception as e:
        logger.exception(f"[RADIO] Error activando modo radio: {e}")
        return JsonResponse({"ok": False, "error": "Error interno"}, status=500)


@login_required
@require_POST
def desactivar_modo_radio(request):
    user = request.user

    canal = CanalTransmision.objects.filter(usuario=user).first()
    if not canal:
        return JsonResponse({"ok": False, "error": "Canal no encontrado"}, status=404)

    if not canal.modo_radio:
        return JsonResponse({"ok": True, "modo": "video", "ya_activo": True})

    # ── Detener feeder radio y esperar que libere el slot ──
    stop_radio_feeder(user)
    time.sleep(2)

    # ── Reiniciar HLS maestro para que vuelva a tomar el flujo de video ──
    logger.info(f"[RADIO] Reiniciando HLS maestro antes de desactivar modo radio")
    stop_program_hls(user)
    time.sleep(1)
    start_program_hls(user)

    camara_on_air = StreamConnection.objects.filter(
        user=user,
        status=StreamConnection.Status.ON_AIR
    ).first()

    if camara_on_air:
        try:
            switch_program_camera(user, camara_on_air.stream_key)
        except Exception as e:
            logger.error(f"[RADIO] Error relanzando feeder de video: {e}")

    canal.desactivar_modo_radio()
    _notificar_modo_radio(user.id, modo_radio=False)
    logger.info(f"[RADIO] Modo radio DESACTIVADO para {user.username}")
    return JsonResponse({"ok": True, "modo": "video"})


@login_required
def estado_modo_radio(request):
    canal = CanalTransmision.objects.filter(usuario=request.user).first()
    return JsonResponse({
        "ok": True,
        "modo_radio": canal.modo_radio if canal else False,
        "en_vivo": canal.en_vivo if canal else False,
    })


@login_required
@require_POST
def subir_imagen_radio(request):
    """Sube o reemplaza la imagen de radio del usuario."""
    user = request.user

    if 'imagen_radio' not in request.FILES:
        return JsonResponse({"ok": False, "error": "No se recibió ninguna imagen"}, status=400)

    imagen = request.FILES['imagen_radio']

    # Validar que sea imagen
    tipos_permitidos = ['image/jpeg', 'image/png', 'image/jpg', 'image/webp']
    if imagen.content_type not in tipos_permitidos:
        return JsonResponse({"ok": False, "error": "Formato no permitido. Usá JPG, PNG o WebP"}, status=400)

    # Carpeta destino: media/radio_images/
    radio_dir = os.path.join(settings.MEDIA_ROOT, "radio_images")
    os.makedirs(radio_dir, exist_ok=True)

    # Nombre del archivo: {username}.{extension}
    extension = imagen.name.rsplit('.', 1)[-1].lower()
    nombre_archivo = f"{user.username}.{extension}"
    ruta_absoluta = os.path.join(radio_dir, nombre_archivo)

    # Si ya existe una imagen anterior con distinta extensión, borrarla
    canal = CanalTransmision.objects.filter(usuario=user).first()
    if canal and canal.radio_imagen_path and os.path.isfile(canal.radio_imagen_path):
        if canal.radio_imagen_path != ruta_absoluta:
            try:
                os.remove(canal.radio_imagen_path)
            except Exception:
                pass

    # Guardar el nuevo archivo
    with open(ruta_absoluta, 'wb+') as f:
        for chunk in imagen.chunks():
            f.write(chunk)

    # Guardar ruta en DB
    if not canal:
        canal = CanalTransmision.objects.create(usuario=user)

    canal.radio_imagen_path = ruta_absoluta
    canal.save(update_fields=['radio_imagen_path'])

    logger.info(f"[RADIO] Imagen subida para {user.username}: {ruta_absoluta}")
    return JsonResponse({
        "ok": True,
        "mensaje": "Imagen guardada correctamente",
        "url_preview": f"{settings.MEDIA_URL}radio_images/{nombre_archivo}"
    })


@login_required
@require_POST
def eliminar_imagen_radio(request):
    """Elimina la imagen de radio del usuario."""
    user = request.user

    canal = CanalTransmision.objects.filter(usuario=user).first()
    if not canal or not canal.radio_imagen_path:
        return JsonResponse({"ok": False, "error": "No hay imagen configurada"}, status=400)

    # Borrar archivo físico
    if os.path.isfile(canal.radio_imagen_path):
        try:
            os.remove(canal.radio_imagen_path)
        except Exception as e:
            logger.warning(f"[RADIO] Error borrando imagen: {e}")

    # Limpiar DB
    canal.radio_imagen_path = ''
    canal.save(update_fields=['radio_imagen_path'])

    logger.info(f"[RADIO] Imagen eliminada para {user.username}")
    return JsonResponse({"ok": True, "mensaje": "Imagen eliminada"})


@login_required
def estado_imagen_radio(request):
    """Devuelve si el usuario tiene imagen configurada y la URL de preview."""
    user = request.user
    canal = CanalTransmision.objects.filter(usuario=user).first()

    if not canal or not canal.radio_imagen_path or not os.path.isfile(canal.radio_imagen_path):
        return JsonResponse({"ok": True, "tiene_imagen": False})

    nombre_archivo = os.path.basename(canal.radio_imagen_path)
    return JsonResponse({
        "ok": True,
        "tiene_imagen": True,
        "url_preview": f"{settings.MEDIA_URL}radio_images/{nombre_archivo}"
    })