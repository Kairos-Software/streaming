import subprocess
from django.conf import settings

# Diccionario global de procesos FFmpeg: {user_id: proceso}
FFMPEG_PROCESSES = {}


def stop_program_stream(user):
    """Detiene el proceso FFmpeg del usuario si existe y limpia el diccionario."""
    proc = FFMPEG_PROCESSES.get(user.id)
    if proc and proc.poll() is None:
        print(f"[DEBUG] Deteniendo FFMPEG para {user.username}")
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
    FFMPEG_PROCESSES.pop(user.id, None)


def start_program_stream(user, stream_key):
    """
    Inicia la retransmisión 'program' desde el RTMP interno.
    Cada usuario mantiene su propio proceso FFmpeg.
    """
    FFMPEG_BIN = settings.FFMPEG_BIN_PATH
    RTMP_HOST = settings.RTMP_SERVER_HOST_INTERNAL
    RTMP_PORT = settings.RTMP_SERVER_PORT_INTERNAL

    # Si ya hay un proceso corriendo para este usuario, no lo reiniciamos
    proc = FFMPEG_PROCESSES.get(user.id)
    if proc and proc.poll() is None:
        print(f"[DEBUG] FFMPEG ya corriendo para {user.username}")
        return

    input_rtmp = f"rtmp://{RTMP_HOST}:{RTMP_PORT}/live/{stream_key}"
    output_rtmp = f"rtmp://{RTMP_HOST}:{RTMP_PORT}/program/{user.username}"

    cmd = [
        FFMPEG_BIN,
        "-re",
        "-i", input_rtmp,
        "-c", "copy",
        "-f", "flv",
        output_rtmp,
    ]

    print(f"[DEBUG] Ejecutando FFMPEG para {user.username}")
    print("CMD:", " ".join(cmd))

    try:
        # Usamos DEVNULL para evitar bloqueos por pipes llenos
        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.STDOUT
        )
    except Exception as e:
        print(f"[ERROR] No se pudo iniciar FFMPEG para {user.username}: {e}")
        return

    FFMPEG_PROCESSES[user.id] = proc
