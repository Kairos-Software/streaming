from django.db import models
from django.contrib.auth.models import User


class Cliente(models.Model):
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
    connected_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("user", "cam_index")
