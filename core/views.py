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


# ===== LOGIN VIEW =====
def login_view(request):
    if request.method == "POST":
        username = request.POST.get("username")
        password = request.POST.get("password")

        user = authenticate(request, username=username, password=password)
        if user is not None:
            login(request, user)
            return redirect("home")  # redirige al home después de login
        else:
            return render(request, "core/login.html", {"error": "Credenciales inválidas"})

    return render(request, "core/login.html")


def logout_view(request):
    logout(request)
    return redirect("login")


@login_required
def home(request):
    base_url = "http://192.168.0.186:8080/hls"

    # conexiones actuales del usuario
    connections = {
        c.cam_index: c
        for c in StreamConnection.objects.filter(user=request.user)
    }

    cameras = []
    current_camera_url = None

    for cam_index in range(1, 7):
        conn = connections.get(cam_index)

        stream_key = f"{request.user.username}-cam{cam_index}"
        hls_url = f"{base_url}/{stream_key}.m3u8"

        status = conn.status if conn else "offline"

        if status == "on_air":
            current_camera_url = hls_url

        cameras.append({
            "index": cam_index,
            "hls_url": hls_url,
            "status": status,
            "has_pending": status == "pending",
            "has_ready": status == "ready",
            "is_on_air": status == "on_air",
        })

    return render(request, "core/home.html", {
        "cameras": cameras,
        "current_camera_url": current_camera_url,
    })


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

    # 🔁 Crear o actualizar conexión (PENDING)
    StreamConnection.objects.update_or_create(
        user=user,
        cam_index=cam_index,
        defaults={
            "stream_key": stream_name,
            "status": "pending",
            "authorized": False,
        }
    )

    # ⚠️ NO autorizamos aún
    return HttpResponse("PENDING", content_type="text/plain")


@require_POST
@login_required
def autorizar_camara(request, cam_index):
    pin_ingresado = request.POST.get("pin")

    if not pin_ingresado:
        return JsonResponse(
            {"ok": False, "error": "PIN faltante"},
            status=400
        )

    cliente = request.user.cliente

    if pin_ingresado != cliente.pin:
        return JsonResponse(
            {"ok": False, "error": "PIN incorrecto"},
            status=403
        )

    try:
        conn = StreamConnection.objects.get(
            user=request.user,
            cam_index=cam_index,
            status="pending"
        )
    except StreamConnection.DoesNotExist:
        return JsonResponse(
            {"ok": False, "error": "No hay solicitud pendiente"},
            status=404
        )

    conn.status = "ready"
    conn.authorized = True
    conn.save()

    return JsonResponse({"ok": True})


@login_required
def rechazar_camara(request, cam_index):
    if request.method != "POST":
        return HttpResponseForbidden()

    StreamConnection.objects.filter(
        user=request.user,
        cam_index=cam_index,
        status="pending"
    ).delete()

    return redirect("home")


@login_required
def set_camera_on_air(request, cam_index):
    if request.method != "POST":
        return HttpResponseForbidden()

    # ❌ Apagar cualquier cámara al aire
    StreamConnection.objects.filter(
        user=request.user,
        status="on_air"
    ).update(status="ready")

    # ✅ Encender la nueva
    try:
        conn = StreamConnection.objects.get(
            user=request.user,
            cam_index=cam_index,
            status="ready"
        )
    except StreamConnection.DoesNotExist:
        return HttpResponseForbidden("Cámara no lista")

    conn.status = "on_air"
    conn.save()

    return redirect("home")


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
        return HttpResponse("USUARIO NO EXISTE", status=404)

    # Buscar conexión activa
    try:
        conn = StreamConnection.objects.get(
            user=user,
            cam_index=cam_index
        )
    except StreamConnection.DoesNotExist:
        # Ya estaba limpia (no pasa nada)
        return HttpResponse("OK")

    # 🧹 BORRAR conexión completamente
    conn.delete()

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


@login_required
def estado_camaras(request):
    """
    Devuelve el estado actual de todas las cámaras del usuario logueado
    en formato JSON para polling desde el frontend.
    """

    conexiones = StreamConnection.objects.filter(user=request.user)

    data = {}

    for conn in conexiones:
        hls_url = None

        # ready = autorizada y transmitiendo
        # on_air = emitida en preview final (más adelante)
        if conn.status in ("ready", "on_air"):
            # ⚠️ HLS PLANO (NO index.m3u8)
            hls_url = f"http://localhost:8080/hls/{conn.stream_key}.m3u8"

        data[str(conn.cam_index)] = {
            "status": conn.status,
            "authorized": conn.authorized,
            "updated_at": conn.updated_at.isoformat(),
            "hls_url": hls_url,
        }

    return JsonResponse({
        "ok": True,
        "cameras": data,
    })


@login_required
@require_POST
def poner_al_aire(request, cam_index):
    # 1. bajar la que estaba al aire
    StreamConnection.objects.filter(
        user=request.user,
        status="on_air"
    ).update(status="ready")

    # 2. subir la nueva
    StreamConnection.objects.filter(
        user=request.user,
        cam_index=cam_index,
        status="ready"
    ).update(status="on_air")

    return JsonResponse({"ok": True})


