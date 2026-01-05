from django.db import models
from django.contrib.auth.models import User

class Cliente(models.Model):
    # --- DATOS PERSONALES Y DE CUENTA ---
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="cliente")
    nombre = models.CharField(max_length=100)
    apellido = models.CharField(max_length=100)
    dni = models.CharField(max_length=20, unique=True)
    telefono = models.CharField(max_length=20, blank=True)
    direccion = models.CharField(max_length=200, blank=True)

    pin = models.CharField(max_length=10, blank=True, null=True,
                           help_text="PIN para confirmar conexión desde el panel")

    activo = models.BooleanField(default=True)
    creado_en = models.DateTimeField(auto_now_add=True)
    actualizado_en = models.DateTimeField(auto_now=True)

    # --- PERFIL PÚBLICO (REDES SOCIALES Y BIO) ---
    bio = models.TextField(blank=True, null=True, verbose_name="Biografía")
    instagram = models.CharField(max_length=200, blank=True, null=True)
    x_twitter = models.CharField(max_length=200, blank=True, null=True)
    facebook = models.CharField(max_length=200, blank=True, null=True)
    youtube = models.CharField(max_length=200, blank=True, null=True)
    discord = models.CharField(max_length=200, blank=True, null=True)
    tiktok = models.CharField(max_length=200, blank=True, null=True)

    # --- NUEVOS CAMPOS: PREFERENCIAS DE SITIO ---
    pref_autoplay = models.BooleanField(default=True, verbose_name="Reproducción Automática")
    pref_modo_teatro = models.BooleanField(default=False, verbose_name="Modo Teatro por defecto")
    pref_emails = models.BooleanField(default=True, verbose_name="Recibir notificaciones por correo")

    # --- CONFIGURACIÓN DE NOTIFICACIONES ---
    notif_live = models.BooleanField(default=True, verbose_name="Alerta de Transmisión")
    notif_chat_mentions = models.BooleanField(default=True, verbose_name="Menciones en Chat")
    notif_marketing = models.BooleanField(default=False, verbose_name="Novedades y Ofertas")

    def __str__(self):
        return f"{self.nombre} {self.apellido} ({self.user.email})"


class StreamConnection(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "Pendiente"
        READY = "ready", "Lista"
        ON_AIR = "on_air", "Al aire"
        OFFLINE = "offline", "Desconectada"

    user = models.ForeignKey(User, on_delete=models.CASCADE)
    cam_index = models.PositiveIntegerField()
    stream_key = models.CharField(max_length=100)

    status = models.CharField(
        max_length=10,
        choices=Status.choices,
        default=Status.PENDING,
    )

    authorized = models.BooleanField(default=False)

    conectado_en = models.DateTimeField(
        auto_now_add=True,
        help_text="Momento en que nginx detectó la conexión RTMP"
    )

    ultimo_contacto = models.DateTimeField(
        auto_now=True,
        help_text="Última señal recibida desde nginx RTMP"
    )

    class Meta:
        unique_together = ("user", "cam_index")


class CanalTransmision(models.Model):
    usuario = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name="canal_transmision"
    )

    en_vivo = models.BooleanField(default=False)

    url_hls = models.CharField(
        max_length=255,
        blank=True,
        help_text="URL HLS pública del stream final"
    )

    inicio_transmision = models.DateTimeField(
        null=True,
        blank=True
    )

    actualizado_en = models.DateTimeField(auto_now=True)

    def __str__(self):
        estado = "EN VIVO" if self.en_vivo else "OFFLINE"
        return f"{self.usuario.username} - {estado}"
