import subprocess
import signal
import os
import shutil
from django.conf import settings

# Detectar FFmpeg: primero intenta variable de entorno, luego auto-detección
FFMPEG_BIN = os.environ.get('FFMPEG_BIN')

if not FFMPEG_BIN:
    # En Windows (desarrollo)
    if os.name == 'nt':
        FFMPEG_BIN = r"D:\nginx-rtmp\ffmpeg\bin\ffmpeg.exe"
    else:
        # En Linux (producción) - intentar encontrar en PATH
        ffmpeg_path = shutil.which('ffmpeg')
        if ffmpeg_path:
            FFMPEG_BIN = ffmpeg_path
        else:
            # Rutas comunes en Linux
            common_paths = [
                '/usr/bin/ffmpeg',
                '/usr/local/bin/ffmpeg',
            ]
            for path in common_paths:
                if os.path.exists(path):
                    FFMPEG_BIN = path
                    break
            
            if not FFMPEG_BIN:
                raise RuntimeError(
                    "FFmpeg no encontrado. Por favor, instálalo o configura FFMPEG_BIN como variable de entorno"
                )

# Diccionario para guardar los procesos: {user_id: proceso}
FFMPEG_PROCESSES = {}

def stop_program_stream(user):
    """Detiene el proceso FFmpeg del usuario."""
    proc = FFMPEG_PROCESSES.get(user.id)

    if proc and proc.poll() is None:
        # Usamos terminate() que es más estándar, pero send_signal también sirve
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill() # Forzamos cierre si se traba

    FFMPEG_PROCESSES.pop(user.id, None)


def start_program_stream(user, stream_key):
    """Inicia la retransmisión usando RTMP interno configurado."""
    stop_program_stream(user)

    # Usar configuración de settings (por defecto localhost:9000)
    rtmp_host = settings.RTMP_INTERNAL_HOST
    rtmp_port = settings.RTMP_INTERNAL_PORT
    input_rtmp = f"rtmp://{rtmp_host}:{rtmp_port}/live/{stream_key}"
    output_rtmp = f"rtmp://{rtmp_host}:{rtmp_port}/program/{user.username}"

    cmd = [
        FFMPEG_BIN,
        "-re",
        "-i", input_rtmp,
        "-c", "copy",
        "-f", "flv",
        output_rtmp,
    ]

    # Ejecutamos en segundo plano
    proc = subprocess.Popen(
        cmd,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )

    FFMPEG_PROCESSES[user.id] = proc