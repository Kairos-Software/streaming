import os
import glob
from django.conf import settings


def limpiar_hls_usuario(username):
    """
    Elimina SOLO los archivos HLS de un usuario.
    Seguro para múltiples transmisiones concurrentes.
    """

    hls_dir = os.path.join(settings.HLS_PATH, "program")

    if not os.path.exists(hls_dir):
        return

    patrones = [
        f"{username}.m3u8",
        f"{username}_*.ts",
    ]

    eliminados = 0

    for patron in patrones:
        ruta = os.path.join(hls_dir, patron)
        for archivo in glob.glob(ruta):
            try:
                os.remove(archivo)
                eliminados += 1
            except Exception as e:
                print(f"[WARN] No se pudo borrar {archivo}: {e}")

    print(f"[DEBUG] HLS limpiado para {username}: {eliminados} archivos")
