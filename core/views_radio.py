"""
Vistas para Modo Radio.
No modifica views.py existente.
"""
import logging
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.contrib.auth.decorators import login_required
from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer

from core.models import CanalTransmision, StreamConnection
from core.services.radio_manager import start_radio_feeder, stop_radio_feeder
from core.services.ffmpeg_manager import switch_program_camera

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
        return JsonResponse({"ok": False, "error": "No hay cámara al aire para tomar el audio"}, status=400)

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

    stop_radio_feeder(user)

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