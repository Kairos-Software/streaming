import json
import logging

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import render, redirect
from django.views.decorators.http import require_http_methods

from multistream.forms import CuentaYouTubeForm
from multistream.models import CuentaYouTube, EstadoRetransmision
from multistream.streaming import StreamingManager

logger = logging.getLogger(__name__)


@login_required
def ajustes_retransmision(request):
    """
    Configuración de cuentas de retransmisión (YouTube, futuro: FB, TikTok, etc)
    """
    cuenta_youtube = CuentaYouTube.objects.filter(usuario=request.user).first()

    if request.method == "POST":
        form = CuentaYouTubeForm(request.POST, instance=cuenta_youtube)
        if form.is_valid():
            cuenta = form.save(commit=False)
            cuenta.usuario = request.user
            cuenta.save()
            messages.success(request, "✅ Configuración de YouTube guardada correctamente")
            return redirect("ajustes_retransmision")
        else:
            messages.error(request, "❌ Error al guardar la configuración")
    else:
        form = CuentaYouTubeForm(instance=cuenta_youtube)

    return render(request, "multistream/retransmision.html", {
        "active_tab": "retransmision",
        "form_youtube": form,
        "cuenta_youtube": cuenta_youtube,
    })


@login_required
@require_http_methods(["POST"])
def iniciar_retransmision(request):
    """
    API
    POST JSON:
    {
        "platforms": ["youtube", "facebook"]
    }
    """
    try:
        payload = json.loads(request.body)
        platforms = payload.get("platforms", [])

        if not platforms:
            return JsonResponse({
                "ok": False,
                "error": "No se seleccionaron plataformas"
            }, status=400)

        manager = StreamingManager(request.user)
        resultados = []

        for platform in platforms:
            resultado = manager.iniciar_plataforma(platform)
            resultados.append({
                "platform": platform,
                "success": resultado["success"],
                "message": resultado.get("message", "")
            })

        return JsonResponse({
            "ok": any(r["success"] for r in resultados),
            "resultados": resultados
        })

    except json.JSONDecodeError:
        return JsonResponse({
            "ok": False,
            "error": "JSON inválido"
        }, status=400)

    except Exception as e:
        logger.exception("Error iniciando retransmisión")
        return JsonResponse({
            "ok": False,
            "error": str(e)
        }, status=500)


@login_required
@require_http_methods(["POST"])
def detener_retransmision(request, platform):
    """
    API
    POST /api/restream/stop/<platform>/
    """
    try:
        manager = StreamingManager(request.user)
        resultado = manager.detener_plataforma(platform)

        return JsonResponse({
            "ok": resultado["success"],
            "platform": platform,
            "message": resultado.get("message", "")
        })

    except Exception as e:
        logger.exception(f"Error deteniendo {platform}")
        return JsonResponse({
            "ok": False,
            "platform": platform,
            "error": str(e)
        }, status=500)


@login_required
def estado_retransmisiones(request):
    """
    API
    GET /api/restream/status/
    """
    try:
        estados = EstadoRetransmision.objects.filter(
            usuario=request.user
        ).order_by("-iniciado_en")

        data = []

        for estado in estados:
            data.append({
                "plataforma": estado.plataforma,
                "estado": estado.estado,
                "en_vivo": estado.detenido_en is None,
                "iniciado_en": estado.iniciado_en,
                "detenido_en": estado.detenido_en,
                "mensaje_error": estado.mensaje_error,
            })

        return JsonResponse({
            "ok": True,
            "retransmisiones": data
        })

    except Exception as e:
        logger.exception("Error obteniendo estado de retransmisiones")
        return JsonResponse({
            "ok": False,
            "error": str(e)
        }, status=500)
