from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth.models import User
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from django.http import HttpResponse, HttpResponseForbidden, JsonResponse
from django.contrib import messages
from django.utils import timezone
from django.db import transaction
from datetime import timedelta
from .forms import ClienteForm, PinForm
from .models import Cliente, StreamConnection, CanalTransmision

# 🔧 FFmpeg
from core.services.ffmpeg_manager import start_program_stream, stop_program_stream

# 🔔 Notificaciones WS
from core.services.notificaciones_tiempo_real import (
    notificar_actualizacion_camara,
    notificar_camara_eliminada,
    notificar_estado_canal,
)

# 🎥 Estado transmisión
from core.services.estado_transmision import (
    detener_transmision_usuario,
    poner_camara_al_aire,
    cerrar_camara_usuario,
)

# 🌐 VPS host
VPS_HOST = "kaircampanel.grupokairosarg.com"

# =========================
# AUTENTICACIÓN
# =========================

def login_view(request):
    if request.method == "POST":
        user = authenticate(
            request,
            username=request.POST.get("username"),
            password=request.POST.get("password"),
        )
        if user:
            login(request, user)
            return redirect("home")
        return render(request, "core/login.html", {"error": "Credenciales inválidas"})
    return render(request, "core/login.html")

def logout_view(request):
    logout(request)
    return redirect("login")

@login_required
def home(request):
    return render(request, "core/home.html")

# =========================
# RTMP / INGESTA
# =========================

@csrf_exempt
def validar_publicacion_stream_rtmp(request):
    stream_name = request.POST.get("name") or request.GET.get("name")
    if not stream_name:
        return HttpResponseForbidden("Falta stream")

    try:
        username, cam_part = stream_name.split("-cam")
        cam_index = int(cam_part)
    except Exception:
        return HttpResponseForbidden("Formato inválido")

    try:
        user = User.objects.get(username=username)
        cliente = user.cliente
        if not cliente.activo:
            return HttpResponseForbidden("Cliente inactivo")
    except (User.DoesNotExist, Cliente.DoesNotExist):
        return HttpResponseForbidden("Cliente inválido")

    StreamConnection.objects.update_or_create(
        user=user,
        cam_index=cam_index,
        defaults={
            "stream_key": stream_name,
            "status": StreamConnection.Status.PENDING,
            "authorized": False,
        }
    )

    notificar_actualizacion_camara(user, cam_index)
    return HttpResponse("OK", content_type="text/plain")

@csrf_exempt
def stream_finalizado(request):
    stream_name = request.POST.get("name") or request.GET.get("name")
    if not stream_name:
        return HttpResponse("NO STREAM", status=400)

    try:
        username, cam_part = stream_name.split("-cam")
        cam_index = int(cam_part)
    except Exception:
        return HttpResponse("FORMATO INVALIDO", status=400)

    try:
        user = User.objects.get(username=username)
    except User.DoesNotExist:
        return HttpResponse("OK")

    StreamConnection.objects.filter(
        user=user,
        cam_index=cam_index,
    ).delete()

    notificar_camara_eliminada(user, cam_index)
    return HttpResponse("OK")

# =========================
# CÁMARAS
# =========================

@login_required
@require_POST
def autorizar_camara(request, cam_index):
    pin = request.POST.get("pin")
    if not pin or pin != request.user.cliente.pin:
        return JsonResponse({"ok": False, "error": "PIN incorrecto"}, status=403)

    try:
        with transaction.atomic():
            conn = StreamConnection.objects.select_for_update().get(
                user=request.user,
                cam_index=cam_index,
                status=StreamConnection.Status.PENDING,
            )
            conn.status = StreamConnection.Status.READY
            conn.authorized = True
            conn.save(update_fields=["status", "authorized"])
    except StreamConnection.DoesNotExist:
        return JsonResponse({"ok": False, "error": "No hay solicitud pendiente"}, status=404)

    notificar_actualizacion_camara(request.user, cam_index)
    return JsonResponse({"ok": True})

@login_required
@require_POST
def rechazar_camara(request, cam_index):
    StreamConnection.objects.filter(
        user=request.user,
        cam_index=cam_index,
        status=StreamConnection.Status.PENDING,
    ).delete()
    notificar_camara_eliminada(request.user, cam_index)
    return JsonResponse({"ok": True})

@login_required
@require_POST
def cerrar_camara(request, cam_index):
    cerrar_camara_usuario(request.user, cam_index)
    return JsonResponse({"ok": True})

# =========================
# TRANSMISIÓN
# =========================

@login_required
@require_POST
def detener_transmision(request):
    detener_transmision_usuario(request.user)
    return JsonResponse({"ok": True})

@login_required
@require_POST
def poner_al_aire(request, cam_index):
    try:
        poner_camara_al_aire(request.user, cam_index)
    except ValueError as e:
        return JsonResponse({"ok": False, "error": str(e)}, status=400)
    return JsonResponse({"ok": True})

# =========================
# ESTADO / POLLING
# =========================

@login_required
def estado_camaras(request):
    conexiones = StreamConnection.objects.filter(user=request.user)
    data = {}

    for conn in conexiones:
        hls_url = None
        if conn.status in (StreamConnection.Status.READY, StreamConnection.Status.ON_AIR):
            hls_url = f"http://{VPS_HOST}:8080/hls/live/{conn.stream_key}.m3u8"

        data[str(conn.cam_index)] = {
            "status": conn.status,
            "authorized": conn.authorized,
            "hls_url": hls_url,
        }

    return JsonResponse({"ok": True, "cameras": data})

# =========================
# USUARIOS (ADMIN)
# =========================

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

# =========================
# PERFIL CLIENTE
# =========================

@login_required
def gestionar_pin(request):
    try:
        cliente = Cliente.objects.get(user=request.user)
    except Cliente.DoesNotExist:
        messages.error(request, "No se encontró el perfil de cliente asociado.")
        return redirect("home")

    if request.method == "POST":
        form = PinForm(request.POST, instance=cliente)
        if form.is_valid():
            form.save()
            messages.success(request, "¡Tu PIN ha sido actualizado con éxito!")
            return redirect("gestionar_pin")
    else:
        form = PinForm(instance=cliente)

    context = {
        "form": form,
        "cliente": cliente,
        "pin_establecido": bool(cliente.pin),
    }

    return render(request, "core/gestionar_pin.html", context)

# =========================
# VISTAS SIMPLES
# =========================

@login_required
def audio(request):
    return render(request, "core/audio.html")

@login_required
def tutorial(request):
    return render(request, "core/tutorial.html")
