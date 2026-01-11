import qrcode
import io
import base64
from datetime import timedelta
from django.conf import settings
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import authenticate, login, logout, update_session_auth_hash
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth.models import User
from django.contrib.auth.forms import PasswordChangeForm
from django.http import HttpResponse, HttpResponseForbidden, JsonResponse
from django.contrib import messages
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from django.utils import timezone
from core.services.estado_transmision import notificar_estado_inicial_usuario
# --- TERCEROS ---
from django_otp.plugins.otp_totp.models import TOTPDevice

# --- LOCALES ---
from .forms import ClienteForm, PinForm, ProfileSettingsForm, PreferenciasForm, NotificacionesForm
from .models import Cliente, StreamConnection, CanalTransmision
# Servicios Websocket y Lógica
from core.services.notificaciones_tiempo_real import notificar_camara_actualizada, notificar_camara_eliminada, notificar_estado_canal
from core.services.estado_transmision import (
    poner_camara_al_aire,
    detener_transmision_usuario,
    cerrar_camara_usuario,
    limpiar_conexiones_huerfanas
)
# Solo necesitamos stop para cuando Nginx avisa directamente
from core.services.ffmpeg_manager import stop_program_stream 


# ==============================================================================
# SECCIÓN 1: AUTENTICACIÓN Y SEGURIDAD (Sin cambios)
# ==============================================================================

def login_view(request):
    if request.method == "POST":
        username = request.POST.get("username")
        password = request.POST.get("password")
        otp_token = request.POST.get("otp_token")

        user = authenticate(request, username=username, password=password)

        if user:
            device = TOTPDevice.objects.filter(user=user, confirmed=True).first()
            if device:
                if otp_token:
                    if device.verify_token(otp_token):
                        login(request, user)
                        return redirect("home")
                    else:
                        return render(request, "core/login.html", {
                            "error": "Código 2FA incorrecto",
                            "ask_2fa": True,
                            "temp_username": username,
                            "temp_password": password
                        })
                else:
                    return render(request, "core/login.html", {
                        "ask_2fa": True,
                        "temp_username": username,
                        "temp_password": password
                    })
            else:
                login(request, user)
                return redirect("home")

        return render(request, "core/login.html", {"error": "Credenciales inválidas"})

    return render(request, "core/login.html")


@login_required
def configurar_2fa(request):
    user = request.user
    device, created = TOTPDevice.objects.get_or_create(user=user, name="default")
    
    if request.method == 'POST':
        token = request.POST.get('token')
        if device.verify_token(token):
            device.confirmed = True
            device.save()
            messages.success(request, "¡Código correcto! Seguridad activada.")
            return redirect('ajustes_seguridad')
        else:
            messages.error(request, "Código incorrecto.")

    otp_url = device.config_url
    qr = qrcode.make(otp_url)
    buffer = io.BytesIO()
    qr.save(buffer, format="PNG")
    qr_img_str = base64.b64encode(buffer.getvalue()).decode()
    secret_key_clean = base64.b32encode(device.bin_key).decode('utf-8')

    return render(request, 'core/configurar_2fa.html', {
        'qr_image': qr_img_str,
        'secret_key': secret_key_clean
    })


@login_required
def desactivar_2fa(request):
    if request.method == "POST":
        TOTPDevice.objects.filter(user=request.user).delete()
        messages.warning(request, "Autenticación de dos pasos desactivada.")
    return redirect('ajustes_seguridad')


def logout_view(request):
    logout(request)
    return redirect("login")


# ==============================================================================
# SECCIÓN 2: VISTAS PRINCIPALES
# ==============================================================================
@login_required
def home(request):
    notificar_estado_inicial_usuario(request.user)
    return render(request, "core/home.html")


@login_required
def audio(request):
    return render(request, "core/audio.html")

@login_required
def tutorial(request):
    return render(request, "core/tutorial.html")


# ==============================================================================
# SECCIÓN 3: GESTIÓN DE CÁMARAS (USANDO SERVICIOS)
# ==============================================================================
import os
from urllib.parse import urlparse


@csrf_exempt
def validar_publicacion(request):
    tcurl = request.POST.get("tcurl", "")
    stream_key = request.POST.get("name") or request.GET.get("name")
    
    # ---------------------------------------------------------
    # 1. SEGURIDAD DE HOST (Inteligente)
    # ---------------------------------------------------------
    # Solo activamos la seguridad estricta si NO estamos en modo DEBUG (Producción/VPS)
    if not settings.DEBUG:
        host = urlparse(tcurl).hostname or ""
        allowed_host = settings.RTMP_SERVER_HOST_PUBLIC

        if host and host != allowed_host:
            print(f"[ALERTA] Intento de conexión desde host no permitido: {host}")
            return HttpResponseForbidden("Dominio RTMP no permitido")

    # ---------------------------------------------------------
    # 2. VALIDACIÓN DE USUARIO Y KEY
    # ---------------------------------------------------------
    if not stream_key:
        return HttpResponseForbidden("Falta stream key")

    try:
        if "-cam" not in stream_key:
             return HttpResponseForbidden("Formato inválido")
             
        username, cam_part = stream_key.split("-cam")
        cam_index = int(cam_part)
        
        user = User.objects.get(username=username)
        # Verificamos que el cliente tenga perfil y esté activo
        if not hasattr(user, "cliente") or not user.cliente.activo:
            return HttpResponseForbidden("Usuario inactivo")
            
    except (ValueError, User.DoesNotExist):
        return HttpResponseForbidden("Credenciales inválidas")

    # ---------------------------------------------------------
    # 3. REGISTRO DE CONEXIÓN
    # ---------------------------------------------------------
    StreamConnection.objects.update_or_create(
        user=user,
        cam_index=cam_index,
        defaults={
            "stream_key": stream_key,
            "status": StreamConnection.Status.PENDING,
            "authorized": False,
            "ultimo_contacto": timezone.now()
        }
    )

    # Notificar al frontend
    notificar_camara_actualizada(user, cam_index)

    return HttpResponse("OK")


@csrf_exempt
def stream_finalizado(request):
    stream_key = request.POST.get("name") or request.GET.get("name")
    if not stream_key:
        return HttpResponse("OK")

    try:
        username, cam_part = stream_key.split("-cam")
        cam_index = int(cam_part)
        user = User.objects.get(username=username)

        # Solo cerramos la cámara
        cerrar_camara_usuario(user, cam_index)

        # Si ya no queda ninguna ON_AIR → apagamos todo
        hay_on_air = StreamConnection.objects.filter(
            user=user,
            status=StreamConnection.Status.ON_AIR,
        ).exists()

        if not hay_on_air:
            detener_transmision_usuario(user)

        print(f"[DEBUG] stream_finalizado OK: {username} cam {cam_index}")

    except Exception as e:
        print(f"[ERROR] stream_finalizado: {e}")

    return HttpResponse("OK")


@login_required
@require_POST
def autorizar_camara(request, cam_index):
    pin = request.POST.get("pin")
    if not pin or not hasattr(request.user, "cliente") or pin != request.user.cliente.pin:
        return JsonResponse({"ok": False, "error": "PIN incorrecto"}, status=403)

    try:
        conn = StreamConnection.objects.get(
            user=request.user,
            cam_index=cam_index,
            status=StreamConnection.Status.PENDING
        )
        conn.status = StreamConnection.Status.READY
        conn.authorized = True
        conn.save()

        # 🔔 Notificación WebSocket
        notificar_camara_actualizada(request.user, cam_index)

        print(f"[DEBUG] autorizar_camara: usuario {request.user.username} cam {cam_index} READY")
        return JsonResponse({"ok": True})

    except StreamConnection.DoesNotExist:
        return JsonResponse({"ok": False, "error": "Solicitud no encontrada"}, status=404)


@login_required
@require_POST
def poner_al_aire(request, cam_index):
    try:
        poner_camara_al_aire(request.user, cam_index)
        print(f"[DEBUG] poner_al_aire: usuario {request.user.username} cam {cam_index} ON_AIR")
        return JsonResponse({"ok": True})
    except ValueError as e:
        return JsonResponse({"ok": False, "error": str(e)}, status=400)
    except Exception as e:
        print(f"[ERROR] poner_al_aire: {e}")
        return JsonResponse({"ok": False, "error": "Error interno"}, status=500)


@login_required
@require_POST
def detener_transmision(request):
    detener_transmision_usuario(request.user)
    print(f"[DEBUG] detener_transmision: usuario {request.user.username}")
    return JsonResponse({"ok": True})


@login_required
@require_POST
def rechazar_camara(request, cam_index):
    """
    Frontend -> Django.
    """
    cerrar_camara_usuario(request.user, cam_index)
    return JsonResponse({"ok": True})


@login_required
@require_POST
def cerrar_camara(request, cam_index):
    """
    Frontend -> Django. (Botón 'X').
    """
    cerrar_camara_usuario(request.user, cam_index)
    return JsonResponse({"ok": True})


@login_required
def estado_camaras(request):
    from core.services.estado_transmision import limpiar_conexiones_huerfanas
    from core.models import CanalTransmision

    # --- CORRECCIÓN BUG CORTES AL NAVEGAR ---
    # COMENTAMOS ESTA LÍNEA para evitar que la navegación entre páginas
    # (que desconecta el socket momentáneamente) mate el proceso FFmpeg.
    # limpiar_conexiones_huerfanas(request.user)

    conexiones = StreamConnection.objects.filter(user=request.user)
    data = {}

    for conn in conexiones:
        hls_url = None
        # --- CORRECCIÓN BUG IMÁGENES DUPLICADAS ---
        # Siempre devolvemos la URL de la fuente (live) para las tarjetas de cámara,
        # incluso si están ON_AIR. El preview principal usará la del canal (program).
        if conn.status in [StreamConnection.Status.READY, StreamConnection.Status.ON_AIR]:
            hls_url = f"{settings.HLS_BASE_URL}/live/{conn.stream_key}.m3u8"

        data[str(conn.cam_index)] = {
            "status": conn.status,
            "authorized": conn.authorized,
            "hls_url": hls_url,
        }

    canal_obj = CanalTransmision.objects.filter(usuario=request.user).first()
    canal = None
    if canal_obj:
        canal = {
            "en_vivo": bool(canal_obj.en_vivo),
            "hls_url": canal_obj.url_hls,
            "inicio": canal_obj.inicio_transmision.isoformat() if canal_obj.inicio_transmision else None,
        }

    return JsonResponse({"ok": True, "cameras": data, "canal": canal})


# ==============================================================================
# SECCIÓN 4: ADMIN Y EXTRAS (Sin cambios)
# ==============================================================================

@user_passes_test(lambda u: u.is_superuser)
def crear_usuario(request):
    if request.method == "POST":
        form = ClienteForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect("home") 
    else:
        form = ClienteForm()
    return render(request, "core/crear_usuario.html", {"form": form})


@user_passes_test(lambda u: u.is_superuser)
def ver_usuarios(request):
    clientes = Cliente.objects.select_related("user").all()
    return render(request, "core/ver_usuarios.html", {"clientes": clientes})


@user_passes_test(lambda u: u.is_superuser)
def editar_usuario(request, pk):
    cliente = get_object_or_404(Cliente, pk=pk)

    if request.method == "POST":
        form = ClienteForm(request.POST, instance=cliente)
        if form.is_valid():
            cliente = form.save(commit=False)
            cliente.activo = "activo" in request.POST
            cliente.save()
            return redirect("ver_usuarios")
    else:
        form = ClienteForm(instance=cliente)

    clientes = Cliente.objects.select_related("user").all()
    return render(request, "core/ver_usuarios.html", {
        "clientes": clientes,
        "form": form,
        "edit_cliente": cliente,
    })


@user_passes_test(lambda u: u.is_superuser)
def eliminar_usuario(request, pk):
    cliente = get_object_or_404(Cliente, pk=pk)
    user = cliente.user

    if request.method == "POST":
        user.delete() 
        return redirect("ver_usuarios")
    return redirect("ver_usuarios")


# --- AJUSTES DE PERFIL (Igual que antes) ---

@login_required
def gestionar_pin(request):
    try:
        # Intentamos obtener el cliente
        cliente = Cliente.objects.get(user=request.user)
    except Cliente.DoesNotExist:
        # SI NO EXISTE y es superusuario, lo creamos automáticamente
        if request.user.is_superuser:
            cliente = Cliente.objects.create(user=request.user)
            messages.success(request, "Se ha creado un perfil de Cliente para el Administrador.")
        else:
            # Si es un usuario normal sin cliente, error
            messages.error(request, "No se encontró el perfil de cliente asociado.")
            return redirect('home')

    if request.method == 'POST':
        form = PinForm(request.POST, instance=cliente)
        if form.is_valid():
            form.save()
            messages.success(request, '¡Tu PIN ha sido actualizado con éxito!')
            return redirect('gestionar_pin')
    else:
        form = PinForm(instance=cliente)

    pin_establecido = bool(cliente.pin)
    
    return render(request, 'core/gestionar_pin.html', {
        'form': form,
        'cliente': cliente,
        'pin_establecido': pin_establecido
    })


@login_required
def ajustes_perfil(request):
    user = request.user
    try:
        cliente = user.cliente
    except Cliente.DoesNotExist:
        messages.error(request, "Tu usuario no tiene un perfil de cliente asociado.")
        return redirect('home')

    if request.method == 'POST':
        form = ProfileSettingsForm(request.POST, request.FILES, instance=cliente, user_instance=user)
        if form.is_valid():
            form.save()
            messages.success(request, '¡Tu perfil ha sido actualizado!')
            return redirect('ajustes_perfil')
    else:
        form = ProfileSettingsForm(instance=cliente, user_instance=user)

    return render(request, 'core/ajustes/perfil.html', {
        'form': form,
        'active_tab': 'perfil'
    })


@login_required
def ajustes_seguridad(request):
    if request.method == 'POST' and 'btn_password' in request.POST:
        password_form = PasswordChangeForm(request.user, request.POST)
        if password_form.is_valid():
            user = password_form.save()
            update_session_auth_hash(request, user) 
            messages.success(request, '¡Tu contraseña ha sido actualizada correctamente!')
            return redirect('ajustes_seguridad')
        else:
            messages.error(request, 'Error al cambiar la contraseña.')
    else:
        password_form = PasswordChangeForm(request.user)

    device = TOTPDevice.objects.filter(user=request.user, confirmed=True).first()
    is_2fa_enabled = bool(device)

    return render(request, 'core/ajustes/seguridad.html', {
        'password_form': password_form,
        'is_2fa_enabled': is_2fa_enabled,
        'active_tab': 'seguridad'
    })


@login_required
def ajustes_preferencias(request):
    try:
        cliente = request.user.cliente
    except Cliente.DoesNotExist:
        return redirect('home')

    if request.method == 'POST':
        form = PreferenciasForm(request.POST, instance=cliente)
        if form.is_valid():
            form.save()
            messages.success(request, "¡Preferencias guardadas!")
            return redirect('ajustes_preferencias')
    else:
        form = PreferenciasForm(instance=cliente)

    return render(request, 'core/ajustes/preferencias.html', {
        'form': form,
        'active_tab': 'preferencias'
    })


@login_required
def ajustes_notificaciones(request):
    try:
        cliente = request.user.cliente
    except Cliente.DoesNotExist:
        return redirect('home')

    if request.method == 'POST':
        form = NotificacionesForm(request.POST, instance=cliente)
        if form.is_valid():
            form.save()
            messages.success(request, "¡Notificaciones guardadas!")
            return redirect('ajustes_notificaciones')
    else:
        form = NotificacionesForm(instance=cliente)

    return render(request, 'core/ajustes/notificaciones.html', {
        'form': form,
        'active_tab': 'notificaciones'
    })


@login_required
def ajustes_conexiones(request):
    rtmp_url = f"rtmp://{settings.RTMP_SERVER_HOST_PUBLIC}:{settings.RTMP_SERVER_PORT}/live"
    stream_key = f"{request.user.username}-cam1"

    return render(request, 'core/ajustes/conexiones.html', {
        'rtmp_url': rtmp_url,
        'stream_key': stream_key,
        'active_tab': 'conexiones'
    })