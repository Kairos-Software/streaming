from django.db import models
from django.contrib.auth.models import User


class CuentaSocialBase(models.Model):
    """
    Clase abstracta que define los campos mínimos comunes
    para cualquier cuenta de retransmisión externa.
    """

    usuario = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name="%(class)s"
    )

    # --- STREAMING ---
    clave_transmision = models.CharField(
        max_length=200,
        help_text="Clave RTMP de la plataforma"
    )
    url_ingestion = models.CharField(
        max_length=255,
        help_text="URL base para ingestión RTMP"
    )

    activo = models.BooleanField(
        default=True,
        help_text="Si la cuenta está habilitada para retransmisión"
    )

    # NUEVO: Campos para tracking
    creado_en = models.DateTimeField(auto_now_add=True)
    actualizado_en = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class CuentaYouTube(CuentaSocialBase):
    """
    Cuenta de YouTube asociada a un usuario.
    """

    id_canal = models.CharField(
        max_length=100,
        blank=True,
        help_text="ID único del canal de YouTube"
    )
    nombre_canal = models.CharField(
        max_length=200,
        blank=True,
        help_text="Nombre público del canal"
    )

    class Meta:
        verbose_name = "Cuenta YouTube"
        verbose_name_plural = "Cuentas YouTube"

    def __str__(self):
        return f"YouTube: {self.nombre_canal or self.usuario.username}"


# =========================================
# 🆕 NUEVO: Agregar esto al final
# =========================================
class EstadoRetransmision(models.Model):
    """
    Trackea el estado de las retransmisiones activas
    """
    ESTADO_CHOICES = [
        ('iniciando', 'Iniciando'),
        ('activo', 'Activo'),
        ('error', 'Error'),
        ('detenido', 'Detenido'),
    ]

    PLATAFORMA_CHOICES = [
        ('youtube', 'YouTube'),
        ('facebook', 'Facebook'),
        ('twitch', 'Twitch'),
        ('instagram', 'Instagram'),
    ]

    usuario = models.ForeignKey(User, on_delete=models.CASCADE, related_name='retransmisiones')
    plataforma = models.CharField(max_length=20, choices=PLATAFORMA_CHOICES)
    estado = models.CharField(max_length=20, choices=ESTADO_CHOICES, default='iniciando')
    
    proceso_id = models.IntegerField(null=True, blank=True, help_text="PID del proceso FFmpeg")
    
    iniciado_en = models.DateTimeField(auto_now_add=True)
    detenido_en = models.DateTimeField(null=True, blank=True)
    
    mensaje_error = models.TextField(blank=True)

    class Meta:
        verbose_name = "Estado de Retransmisión"
        verbose_name_plural = "Estados de Retransmisión"
        ordering = ['-iniciado_en']

    def __str__(self):
        return f"{self.usuario.username} - {self.plataforma} ({self.estado})"