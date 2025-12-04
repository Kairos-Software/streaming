from django.db import models


class Camera(models.Model):
    name = models.CharField(max_length=50)
    stream_key = models.CharField(max_length=50, unique=True)
    hls_path = models.CharField(max_length=200)  # ej: /hls/cam1.m3u8
    active = models.BooleanField(default=True)

    def __str__(self):
        return self.name
