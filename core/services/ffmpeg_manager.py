import os
import subprocess
import signal
from django.conf import settings
from core.services.limpieza_hls import limpiar_hls_usuario

# ============================================================
# PROCESOS FFmpeg EN MEMORIA (1 por usuario)
# ============================================================

PROGRAM_HLS_PROCESSES = {}      # FFmpeg que genera HLS FINAL (NO se reinicia)
PROGRAM_FEEDER_PROCESSES = {}   # FFmpeg feeder (se mata y recrea al switchear cámara)


# ============================================================
# HLS MAESTRO (UNO POR USUARIO)
# ============================================================

def start_program_hls(user):
    """
    Inicia el FFmpeg MAESTRO que:
    RTMP program_switch → HLS en /program
    """

    if user.id in PROGRAM_HLS_PROCESSES:
        proc = PROGRAM_HLS_PROCESSES[user.id]
        if proc.poll() is None:
            print(f"[DEBUG] HLS maestro ya activo para {user.username}")
            return

    FFMPEG_BIN = settings.FFMPEG_BIN_PATH
    RTMP_HOST = settings.RTMP_SERVER_HOST_INTERNAL
    RTMP_PORT = settings.RTMP_SERVER_PORT_INTERNAL
    HLS_PATH = settings.HLS_PATH

    program_dir = os.path.join(HLS_PATH, "program")
    os.makedirs(program_dir, exist_ok=True)

    playlist = os.path.join(program_dir, f"{user.username}.m3u8")
    segments = os.path.join(program_dir, f"{user.username}_%05d.ts")

    cmd = [
        FFMPEG_BIN,
        "-fflags", "+genpts",
        "-use_wallclock_as_timestamps", "1",
        "-i", f"rtmp://{RTMP_HOST}:{RTMP_PORT}/program_switch/{user.username}",

        # Reencode video
        "-c:v", "libx264",
        "-preset", "veryfast",
        "-tune", "zerolatency",
        "-pix_fmt", "yuv420p",
        "-r", "30",
        "-g", "30",              # 🔧 REDUCIDO: de 60 a 30
        "-keyint_min", "30",     # 🔧 REDUCIDO: de 60 a 30
        "-sc_threshold", "0",

        # Reencode audio
        "-c:a", "aac",
        "-b:a", "128k",
        "-ar", "44100",
        "-ac", "2",

        # HLS FINAL
        "-f", "hls",
        "-hls_time", "2",
        "-hls_list_size", "15",
        "-hls_flags", "delete_segments+program_date_time",
        "-hls_segment_filename", segments,
        playlist,
    ]

    print(f"[DEBUG] Iniciando HLS maestro para {user.username}")
    print("CMD HLS:", " ".join(cmd))

    proc = subprocess.Popen(
        cmd,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.STDOUT,
        creationflags=subprocess.CREATE_NEW_PROCESS_GROUP if os.name == "nt" else 0
    )

    PROGRAM_HLS_PROCESSES[user.id] = proc


# ============================================================
# FEEDER (SWITCH DE CÁMARA)
# ============================================================

def switch_program_camera(user, stream_key):
    """
    Cambia la cámara EN VIVO:
    - Mata feeder anterior
    - Inicia feeder nuevo
    - El HLS maestro NO se corta
    """

    old = PROGRAM_FEEDER_PROCESSES.get(user.id)
    if old and old.poll() is None:
        print(f"[DEBUG] Deteniendo feeder anterior ({user.username})")
        try:
            old.terminate()
            old.wait(timeout=5)
        except Exception:
            old.kill()

    PROGRAM_FEEDER_PROCESSES.pop(user.id, None)

    FFMPEG_BIN = settings.FFMPEG_BIN_PATH
    RTMP_HOST = settings.RTMP_SERVER_HOST_INTERNAL
    RTMP_PORT = settings.RTMP_SERVER_PORT_INTERNAL

    input_rtmp = f"rtmp://{RTMP_HOST}:{RTMP_PORT}/live/{stream_key}"
    output_rtmp = f"rtmp://{RTMP_HOST}:{RTMP_PORT}/program_switch/{user.username}"

    feeder_cmd = [
        FFMPEG_BIN,
        "-fflags", "+genpts",
        "-i", input_rtmp,

        # Forzar reencode de video
        "-c:v", "libx264",
        "-preset", "ultrafast",
        "-tune", "zerolatency",
        "-pix_fmt", "yuv420p",
        "-r", "30",
        "-g", "30",              # 🔧 REDUCIDO: de 60 a 30
        "-keyint_min", "30",     # 🔧 REDUCIDO: de 60 a 30
        "-sc_threshold", "0",
        "-force_key_frames", "expr:gte(t,0)",  # 🔧 NUEVO: keyframe inmediato

        # Reencode de audio
        "-c:a", "aac",
        "-b:a", "128k",
        "-ar", "44100",
        "-ac", "2",

        # 🔒 Map explícito para incluir video + audio
        "-map", "0:v:0",
        "-map", "0:a:0",

        "-f", "flv",
        output_rtmp,
    ]

    print(f"[DEBUG] Iniciando feeder → {stream_key}")
    print("CMD FEEDER:", " ".join(feeder_cmd))

    feeder_proc = subprocess.Popen(
        feeder_cmd,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.STDOUT,
        creationflags=subprocess.CREATE_NEW_PROCESS_GROUP if os.name == "nt" else 0
    )

    PROGRAM_FEEDER_PROCESSES[user.id] = feeder_proc


# ============================================================
# FIN REAL DEL EVENTO
# ============================================================

def stop_program_hls(user):
    """
    Detiene TODOS los procesos FFmpeg del usuario y resetea el canal program_switch.
    """
    
    # 1. Matar el feeder
    feeder_proc = PROGRAM_FEEDER_PROCESSES.get(user.id)
    if feeder_proc and feeder_proc.poll() is None:
        print(f"[DEBUG] Deteniendo feeder para {user.username}")
        try:
            feeder_proc.terminate()
            feeder_proc.wait(timeout=5)
        except Exception as e:
            print(f"[WARN] Error al terminar feeder: {e}")
            feeder_proc.kill()
    
    # 2. Matar el HLS maestro
    hls_proc = PROGRAM_HLS_PROCESSES.get(user.id)
    if hls_proc and hls_proc.poll() is None:
        print(f"[DEBUG] Deteniendo HLS maestro para {user.username}")
        try:
            hls_proc.terminate()
            hls_proc.wait(timeout=5)
        except Exception as e:
            print(f"[WARN] Error al terminar HLS maestro: {e}")
            hls_proc.kill()
    
    # 3. Limpiar de los diccionarios
    PROGRAM_FEEDER_PROCESSES.pop(user.id, None)
    PROGRAM_HLS_PROCESSES.pop(user.id, None)

    # 4. Resetear el canal RTMP program_switch (flush)
    FFMPEG_BIN = settings.FFMPEG_BIN_PATH
    RTMP_HOST = settings.RTMP_SERVER_HOST_INTERNAL
    RTMP_PORT = settings.RTMP_SERVER_PORT_INTERNAL

    reset_cmd = [
        FFMPEG_BIN,
        "-f", "lavfi",
        "-i", "anullsrc",
        "-t", "1",
        "-f", "flv",
        f"rtmp://{RTMP_HOST}:{RTMP_PORT}/program_switch/{user.username}",
    ]

    try:
        subprocess.Popen(
            reset_cmd,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=subprocess.CREATE_NEW_PROCESS_GROUP if os.name == "nt" else 0
        )
        print(f"[DEBUG] Canal program_switch reseteado para {user.username}")
    except Exception as e:
        print(f"[WARN] No se pudo resetear program_switch: {e}")
    
    print(f"[DEBUG] stop_program_hls completado para {user.username}")