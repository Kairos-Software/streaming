"""
VIEWS - Multistream
Endpoints para configuración y control de retransmisiones multi-plataforma.
"""

import json
import logging

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import render, redirect
from django.views.decorators.http import require_http_methods

from multistream.forms import CuentaYouTubeForm, CuentaFacebookForm
from multistream.models import CuentaYouTube, CuentaFacebook, EstadoRetransmision
from multistream.services import StreamManager

logger = logging.getLogger(__name__)


@login_required
def ajustes_retransmision(request):
    """
    Página de configuración de cuentas de retransmisión.
    
    Soporta: YouTube, Facebook
    Futuro: TikTok, Twitch, Kick, etc.
    """
    # Obtener cuentas existentes
    cuenta_youtube = CuentaYouTube.objects.filter(usuario=request.user).first()
    cuenta_facebook = CuentaFacebook.objects.filter(usuario=request.user).first()

    if request.method == "POST":
        # Determinar qué formulario se envió
        platform = request.POST.get('platform')
        
        if platform == 'youtube':
            form = CuentaYouTubeForm(request.POST, instance=cuenta_youtube)
            if form.is_valid():
                cuenta = form.save(commit=False)
                cuenta.usuario = request.user
                cuenta.save()
                messages.success(request, "✅ Configuración de YouTube guardada correctamente")
                return redirect("ajustes_retransmision")
            else:
                messages.error(request, "❌ Error al guardar la configuración de YouTube")
        
        elif platform == 'facebook':
            form = CuentaFacebookForm(request.POST, instance=cuenta_facebook)
            if form.is_valid():
                cuenta = form.save(commit=False)
                cuenta.usuario = request.user
                cuenta.save()
                messages.success(request, "✅ Configuración de Facebook guardada correctamente")
                return redirect("ajustes_retransmision")
            else:
                messages.error(request, "❌ Error al guardar la configuración de Facebook")
    
    # GET request - mostrar formularios
    form_youtube = CuentaYouTubeForm(instance=cuenta_youtube)
    form_facebook = CuentaFacebookForm(instance=cuenta_facebook)

    return render(request, "multistream/retransmision.html", {
        "active_tab": "retransmision",
        "form_youtube": form_youtube,
        "form_facebook": form_facebook,
        "cuenta_youtube": cuenta_youtube,
        "cuenta_facebook": cuenta_facebook,
    })


@login_required
@require_http_methods(["POST"])
def iniciar_retransmision(request):
    """
    API - Inicia retransmisión en una o más plataformas.
    
    Request:
        POST /multistream/api/restream/start/
        Body: {
            "platforms": ["youtube", "facebook"],
            "force": false  // Opcional: true para forzar si hay transmisión activa
        }
    
    Response:
        {
            "ok": true/false,
            "resultados": [
                {
                    "platform": "youtube",
                    "success": true,
                    "message": "",
                    "requires_confirmation": false  // true si necesita confirmación del usuario
                },
                ...
            ]
        }
    """
    try:
        # Parsear JSON
        payload = json.loads(request.body)
        platforms = payload.get("platforms", [])
        force = payload.get("force", False)  # Nuevo parámetro

        if not platforms:
            return JsonResponse({
                "ok": False,
                "error": "No se seleccionaron plataformas"
            }, status=400)

        logger.info(f"🎬 {request.user.username} solicita retransmisión en: {platforms} (force={force})")

        # Iniciar cada plataforma
        resultados = []
        for platform in platforms:
            resultado = StreamManager.start_stream(request.user, platform, force=force)
            
            resultados.append({
                "platform": platform,
                "success": resultado["success"],
                "message": resultado.get("message", ""),
                "requires_confirmation": resultado.get("requires_confirmation", False)
            })
        
        # Respuesta general: OK si al menos una tuvo éxito
        success_count = sum(1 for r in resultados if r["success"])
        
        return JsonResponse({
            "ok": success_count > 0,
            "resultados": resultados
        })

    except json.JSONDecodeError:
        logger.error("❌ JSON inválido en solicitud de retransmisión")
        return JsonResponse({
            "ok": False,
            "error": "JSON inválido"
        }, status=400)

    except Exception as e:
        logger.exception("❌ Error inesperado iniciando retransmisión")
        return JsonResponse({
            "ok": False,
            "error": "Error interno del servidor"
        }, status=500)


@login_required
@require_http_methods(["POST"])
def detener_retransmision(request, platform):
    """
    API - Detiene retransmisión en una plataforma específica.
    
    Request:
        POST /multistream/api/restream/stop/<platform>/
    
    Response:
        {
            "ok": true/false,
            "platform": "youtube",
            "message": ""
        }
    """
    try:
        logger.info(f"🛑 {request.user.username} solicita detener {platform}")
        
        resultado = StreamManager.stop_stream(request.user, platform)

        return JsonResponse({
            "ok": resultado["success"],
            "platform": platform,
            "message": resultado.get("message", "")
        })

    except Exception as e:
        logger.exception(f"❌ Error deteniendo {platform}")
        return JsonResponse({
            "ok": False,
            "platform": platform,
            "error": "Error interno del servidor"
        }, status=500)


@login_required
def estado_retransmisiones(request):
    """
    API - Obtiene el estado de todas las retransmisiones del usuario.
    
    Request:
        GET /multistream/api/restream/status/
    
    Response:
        {
            "ok": true,
            "retransmisiones": [
                {
                    "plataforma": "youtube",
                    "estado": "activo",
                    "en_vivo": true,
                    "iniciado_en": "2025-01-26T12:00:00Z",
                    "detenido_en": null,
                    "mensaje_error": ""
                },
                ...
            ]
        }
    """
    try:
        # Obtener estados de BD
        estados = EstadoRetransmision.objects.filter(
            usuario=request.user
        ).order_by("-iniciado_en")[:10]  # Últimas 10

        data = []
        for estado in estados:
            data.append({
                "plataforma": estado.plataforma,
                "estado": estado.estado,
                "en_vivo": estado.detenido_en is None,
                "iniciado_en": estado.iniciado_en.isoformat() if estado.iniciado_en else None,
                "detenido_en": estado.detenido_en.isoformat() if estado.detenido_en else None,
                "mensaje_error": estado.mensaje_error,
            })

        return JsonResponse({
            "ok": True,
            "retransmisiones": data
        })

    except Exception as e:
        logger.exception("❌ Error obteniendo estado de retransmisiones")
        return JsonResponse({
            "ok": False,
            "error": "Error interno del servidor"
        }, status=500)