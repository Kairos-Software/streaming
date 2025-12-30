from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from .forms import ClienteForm, PinForm
from django.contrib.auth.decorators import user_passes_test
from .models import Cliente, StreamConnection, CanalTransmision
from django.http import HttpResponse, HttpResponseForbidden, JsonResponse
from django.contrib import messages
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth.models import User
from django.views.decorators.http import require_POST
from django.utils import timezone
from datetime import timedelta
from django.db import transaction
from core.services.ffmpeg_manager import (start_program_stream,stop_program_stream,)


# Vista encargada de la autenticación de usuarios.
# Recibe credenciales por POST, valida usuario y contraseña y, si son correctas, inicia sesión y redirige al home.
# En caso de error, vuelve a mostrar el formulario con un mensaje de credenciales inválidas.
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


# Cierra la sesión del usuario autenticado y lo redirige a la pantalla de login.
def logout_view(request):
    logout(request)
    return redirect("login")


# Vista principal del panel del usuario autenticado.
# Renderiza la interfaz desde donde el usuario gestiona cámaras, transmisiones y estado general del sistema.
@login_required
def home(request):
    return render(request, "core/home.html")


# Endpoint llamado directamente por NGINX RTMP cuando una cámara intenta iniciar una transmisión.
# Valida que el stream tenga el formato correcto (usuario-camX), que el usuario exista y esté activo.
# Si todo es válido, crea o reutiliza un registro de StreamConnection en estado PENDING, dejando la autorización en manos del usuario desde el panel.
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

    return HttpResponse("OK", content_type="text/plain")


# Autoriza una cámara que está pendiente de conexión.
# Valida el PIN del usuario y, si es correcto, cambia el estado de la cámara de PENDING a READY de forma transaccional para evitar condiciones de carrera.
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


# Rechaza una solicitud de cámara pendiente eliminando su registro.
# Se utiliza cuando el usuario decide no permitir que una cámara se conecte.
@login_required
@require_POST
def rechazar_camara(request, cam_index):
    StreamConnection.objects.filter(
        user=request.user,
        cam_index=cam_index,
        status=StreamConnection.Status.PENDING,
    ).delete()
    return JsonResponse({"ok": True})


# Endpoint llamado por NGINX RTMP cuando una transmisión se corta o finaliza.
# Limpia el registro de la cámara asociada al stream para evitar estados inconsistentes.
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


# Vista exclusiva para superusuarios.
# Permite crear un nuevo usuario/cliente en el sistema mediante un formulario administrativo.
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


# Vista administrativa para superusuarios.
# Lista todos los clientes registrados junto con sus usuarios asociados.
@user_passes_test(lambda u: u.is_superuser)
def ver_usuarios(request):
    clientes = Cliente.objects.select_related("user").all()
    return render(request, "core/ver_usuarios.html", {"clientes": clientes})


# Permite a un superusuario editar los datos de un cliente existente.
# Reutiliza la vista de listado de usuarios mostrando un formulario embebido para edición.
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


# Elimina completamente un usuario y su perfil de cliente asociado.
# La eliminación se hace sobre el usuario, aprovechando la relación OneToOne para borrar el cliente automáticamente.
@user_passes_test(lambda u: u.is_superuser)
def eliminar_usuario(request, pk):
    cliente = get_object_or_404(Cliente, pk=pk)
    user = cliente.user

    if request.method == "POST":
        user.delete()  # Esto elimina también el Cliente por la relación OneToOne
        return redirect("ver_usuarios")

    # Si no es POST, simplemente redirigimos a ver usuarios
    return redirect("ver_usuarios")


# Permite al usuario autenticado crear, ver o modificar su PIN personal.
# El PIN se utiliza como mecanismo de seguridad para autorizar cámaras y transmisiones sensibles.
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


# Función utilitaria interna que elimina conexiones de cámaras que quedaron registradas pero no tuvieron actividad reciente.
# Evita acumulación de estados inválidos cuando una cámara se desconecta abruptamente.
def limpiar_conexiones_huerfanas(usuario=None, segundos_timeout=15):
    """
    Elimina conexiones de cámaras que dejaron de existir realmente.

    Se considera huérfana una cámara si:
    - Está pending, ready u on_air
    - Y no tuvo contacto reciente con el servidor
    """

    limite = timezone.now() - timedelta(seconds=segundos_timeout)

    conexiones = StreamConnection.objects.filter(
        status__in=[
            StreamConnection.Status.PENDING,
            StreamConnection.Status.READY,
            StreamConnection.Status.ON_AIR,
        ],
        conectado_en__lt=limite
    )

    if usuario:
        conexiones = conexiones.filter(user=usuario)

    eliminadas = conexiones.count()
    conexiones.delete()

    return eliminadas


# Endpoint consumido por el frontend (polling).
# Devuelve el estado actual de todas las cámaras del usuario, incluyendo autorización, estado y URL HLS si corresponde.
@login_required
def estado_camaras(request):
    conexiones = StreamConnection.objects.filter(user=request.user)

    data = {}
    for conn in conexiones:
        hls_url = None
        if conn.status in (
            StreamConnection.Status.READY,
            StreamConnection.Status.ON_AIR,
        ):
            hls_url = f"http://localhost:8080/hls/live/{conn.stream_key}.m3u8"

        data[str(conn.cam_index)] = {
            "status": conn.status,
            "authorized": conn.authorized,
            "hls_url": hls_url,
        }

    return JsonResponse({"ok": True, "cameras": data})


# Detiene la transmisión en vivo del usuario.
# Cambia cualquier cámara en estado ON_AIR a READY sin cerrar las conexiones activas.
@login_required
@require_POST
def detener_transmision(request):

    StreamConnection.objects.filter(
        user=request.user,
        status=StreamConnection.Status.ON_AIR
    ).update(status=StreamConnection.Status.READY)

    stop_program_stream(request.user)  # 👈 CLAVE

    canal, _ = CanalTransmision.objects.get_or_create(
        usuario=request.user
    )

    canal.en_vivo = False
    canal.inicio_transmision = None
    canal.save(update_fields=["en_vivo", "inicio_transmision"])

    return JsonResponse({"ok": True})


# Pone una cámara específica al aire.
# Garantiza que solo una cámara esté en estado ON_AIR por usuario, bajando automáticamente cualquier otra activa.
@login_required
@require_POST
def poner_al_aire(request, cam_index):
    with transaction.atomic():

        # Bajamos cualquier otra cámara
        StreamConnection.objects.filter(
            user=request.user,
            status=StreamConnection.Status.ON_AIR,
        ).update(status=StreamConnection.Status.READY)

        # Subimos esta
        conn = StreamConnection.objects.filter(
            user=request.user,
            cam_index=cam_index,
            status=StreamConnection.Status.READY,
        ).first()

        if not conn:
            return JsonResponse(
                {"ok": False, "error": "Cámara no disponible"},
                status=400
            )

        conn.status = StreamConnection.Status.ON_AIR
        conn.save(update_fields=["status"])

        # 🔴 CLAVE: reiniciamos FFmpeg
        stop_program_stream(request.user)
        start_program_stream(
            user=request.user,
            stream_key=conn.stream_key
        )

        canal, _ = CanalTransmision.objects.get_or_create(
            usuario=request.user
        )

        canal.en_vivo = True
        canal.inicio_transmision = timezone.now()
        canal.url_hls = f"http://localhost:8080/hls/program/{request.user.username}.m3u8"
        canal.save()

    return JsonResponse({"ok": True})


# Cierra completamente una cámara, independientemente de su estado actual.
# Elimina el registro de la conexión y fuerza el cierre lógico desde el sistema.
@login_required
@require_POST
def cerrar_camara(request, cam_index):
    """
    Cierra completamente una cámara:
    - PENDING
    - READY
    - ON_AIR
    """
    StreamConnection.objects.filter(
        user=request.user,
        cam_index=cam_index
    ).delete()

    return JsonResponse({"ok": True})


# Renderiza la página de configuración o gestión de audio del sistema para el usuario autenticado.
@login_required
def audio(request):
    return render(request, "core/audio.html")


# Renderiza la página de tutorial o ayuda para el usuario, explicando el uso del panel y las transmisiones.
@login_required
def tutorial(request):
    return render(request, "core/tutorial.html")