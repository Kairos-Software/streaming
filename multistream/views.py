from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.contrib import messages
from multistream.models import CuentaYouTube, EstadoRetransmision
from multistream.forms import CuentaYouTubeForm
from multistream.streaming import StreamingManager
import logging
import json

logger = logging.getLogger(__name__)


@login_required
def ajustes_retransmision(request):
    """Vista para configurar cuentas de retransmisión"""
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
            messages.error(request, "❌ Error al guardar. Verifica los datos.")
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
    API: Iniciar retransmisión en plataformas seleccionadas
    POST: { "platforms": ["youtube", "facebook", ...] }
    """
    try:
        data = json.loads(request.body)
        platforms = data.get('platforms', [])
        
        if not platforms:
            return JsonResponse({
                'ok': False,
                'error': 'No se seleccionaron plataformas'
            }, status=400)
        
        manager = StreamingManager(request.user)
        resultados = []
        
        for platform in platforms:
            resultado = manager.iniciar_plataforma(platform)
            resultados.append({
                'platform': platform,
                'success': resultado['success'],
                'message': resultado.get('message', '')
            })
        
        alguna_exitosa = any(r['success'] for r in resultados)
        
        return JsonResponse({
            'ok': alguna_exitosa,
            'resultados': resultados
        })
        
    except json.JSONDecodeError:
        return JsonResponse({
            'ok': False,
            'error': 'Datos JSON inválidos'
        }, status=400)
    except Exception as e:
        logger.error(f"Error en iniciar_retransmision: {str(e)}")
        return JsonResponse({
            'ok': False,
            'error': str(e)
        }, status=500)


@login_required
@require_http_methods(["POST"])
def detener_retransmision(request, platform):
    """
    API: Detener retransmisión en una plataforma específica
    POST: /api/restream/stop/<platform>/
    """
    try:
        manager = StreamingManager(request.user)
        resultado = manager.detener_plataforma(platform)
        
        return JsonResponse({
            'ok': resultado['success'],
            'message': resultado.get('message', ''),
            'platform': platform
        })
        
    except Exception as e:
        logger.error(f"Error deteniendo {platform}: {str(e)}")
        return JsonResponse({
            'ok': False,
            'error': str(e),
            'platform': platform
        }, status=500)


@login_required
def estado_retransmisiones(request):
    """
    API: Obtener estado de retransmisiones activas
    GET: /api/restream/status/
    """
    try:
        estados = EstadoRetransmision.objects.filter(
            usuario=request.user,
            detenido_en__isnull=True
        ).values('plataforma', 'estado', 'iniciado_en', 'mensaje_error')
        
        return JsonResponse({
            'ok': True,
            'retransmisiones': list(estados)
        })
        
    except Exception as e:
        logger.error(f"Error obteniendo estados: {str(e)}")
        return JsonResponse({
            'ok': False,
            'error': str(e)
        }, status=500)