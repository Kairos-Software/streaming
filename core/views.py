from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from .forms import ClienteForm, PinForm
from django.contrib.auth.decorators import user_passes_test
from .models import Cliente, StreamConnection
from django.http import HttpResponse, HttpResponseForbidden, JsonResponse
from django.contrib import messages
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth.models import User
from django.views.decorators.http import require_POST
from django.utils import timezone
from datetime import timedelta
from django.db import transaction


# ===== LOGIN VIEW =====
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

    return HttpResponse("PENDING", content_type="text/plain")


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

    return JsonResponse({"ok": True})


@login_required
@require_POST
def rechazar_camara(request, cam_index):
    StreamConnection.objects.filter(
        user=request.user,
        cam_index=cam_index,
        status=StreamConnection.Status.PENDING,
    ).delete()
    return JsonResponse({"ok": True})


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

    return HttpResponse("OK")


@user_passes_test(lambda u: u.is_superuser)
def crear_usuario(request):
    if request.method == "POST":
        form = ClienteForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect("home")  # después de crear, redirige a la página principal
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
        user.delete()  # Esto elimina también el Cliente por la relación OneToOne
        return redirect("ver_usuarios")

    # Si no es POST, simplemente redirigimos a ver usuarios
    return redirect("ver_usuarios")


@login_required
def gestionar_pin(request):
    """
    Permite al usuario ver, crear o modificar su PIN.
    """
    try:
        # Intentamos obtener el objeto Cliente asociado al usuario actual
        cliente = Cliente.objects.get(user=request.user)
    except Cliente.DoesNotExist:
        # Esto no debería pasar si la lógica de creación de usuario/cliente es correcta
        messages.error(request, "No se encontró el perfil de cliente asociado.")
        return redirect('otra_vista_segura') # Redirige a una página segura

    # --- Lógica POST (Modificación/Creación) ---
    if request.method == 'POST':
        # Instanciamos el formulario con los datos POST y la instancia de Cliente
        form = PinForm(request.POST, instance=cliente)
        
        if form.is_valid():
            # Guardamos el formulario. Como usamos instance=cliente, se actualiza
            # directamente el campo 'pin' de ese objeto Cliente.
            form.save()
            messages.success(request, '¡Tu PIN ha sido actualizado con éxito!')
            return redirect('gestionar_pin') # Redirige para evitar el doble envío
    
    # --- Lógica GET (Visualización) ---
    else:
        # Para GET, instanciamos el formulario con la instancia de Cliente
        # para que muestre el valor actual del PIN (si existe).
        form = PinForm(instance=cliente)

    # Determinamos el estado para el template
    pin_establecido = bool(cliente.pin)
    
    context = {
        'form': form,
        'cliente': cliente,
        'pin_establecido': pin_establecido
    }
    
    return render(request, 'core/gestionar_pin.html', context)


def limpiar_conexiones_huerfanas(usuario=None, segundos_timeout=15):
    """
    Elimina conexiones de cámaras que no tuvieron actividad reciente.
    Se considera huérfana toda conexión cuya fecha updated_at
    sea anterior al tiempo límite definido.
    """

    limite = timezone.now() - timedelta(seconds=segundos_timeout)

    conexiones = StreamConnection.objects.filter(updated_at__lt=limite)

    if usuario:
        conexiones = conexiones.filter(user=usuario)

    eliminadas = conexiones.count()
    conexiones.delete()

    return eliminadas


@login_required
def estado_camaras(request):
    conexiones = StreamConnection.objects.filter(user=request.user)

    data = {}
    for conn in conexiones:
        hls_url = None
        if conn.status in ("ready", "on_air"):
            hls_url = f"http://localhost:8080/hls/{conn.stream_key}.m3u8"

        data[str(conn.cam_index)] = {
            "status": conn.status,
            "authorized": conn.authorized,
            "hls_url": hls_url,
        }

    return JsonResponse({"ok": True, "cameras": data})


@login_required
@require_POST
def poner_al_aire(request, cam_index):
    with transaction.atomic():
        StreamConnection.objects.filter(
            user=request.user,
            status=StreamConnection.Status.ON_AIR,
        ).update(status=StreamConnection.Status.READY)

        updated = StreamConnection.objects.filter(
            user=request.user,
            cam_index=cam_index,
            status=StreamConnection.Status.READY,
        ).update(status=StreamConnection.Status.ON_AIR)

        if updated == 0:
            return JsonResponse({"ok": False, "error": "Cámara no disponible"}, status=400)

    return JsonResponse({"ok": True})


@login_required
def audio(request):
    return render(request, "core/audio.html")


@login_required
def tutorial(request):
    return render(request, "core/tutorial.html")