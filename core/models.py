from django.db import models
from django.contrib.auth.models import User


# estado de camara 
class BroadcastState(models.Model):
    current_camera = models.CharField(max_length=50, blank=True, null=True,
                                      help_text="Stream key de la cámara actualmente al aire")
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Al aire: {self.current_camera}"


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
    user = models.ForeignKey(User, on_delete=models.CASCADE)

    stream_key = models.CharField(max_length=100)
    cam_index = models.PositiveIntegerField()

    STATUS_CHOICES = [
        ("pending", "Pendiente"),
        ("ready", "Lista"),
        ("on_air", "Al aire"),
    ]
    status = models.CharField(max_length=10, choices=STATUS_CHOICES)

    authorized = models.BooleanField(default=False)

    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ("user", "cam_index")

    def __str__(self):
        return f"{self.user.username} cam{self.cam_index} [{self.status}]"