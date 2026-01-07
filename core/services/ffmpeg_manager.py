import subprocess
from django.conf import settings

FFMPEG_BIN = settings.FFMPEG_BIN_PATH
RTMP_HOST = settings.RTMP_SERVER_HOST_INTERNAL
RTMP_PORT = settings.RTMP_SERVER_PORT_INTERNAL

# Diccionario para guardar los procesos: {user_id: proceso}
FFMPEG_PROCESSES = {}

def stop_program_stream(user):
    """Detiene el proceso FFmpeg del usuario."""
    proc = FFMPEG_PROCESSES.get(user.id)

    if proc and proc.poll() is None:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()

    FFMPEG_PROCESSES.pop(user.id, None)


def start_program_stream(user, stream_key):
    """Inicia la retransmisión usando RTMP interno."""
    stop_program_stream(user)

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

    proc = subprocess.Popen(
        cmd,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )

    FFMPEG_PROCESSES[user.id] = proc
