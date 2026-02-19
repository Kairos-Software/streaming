import os
import subprocess
import time
import threading
from django.conf import settings

# ============================================================
# PROCESOS FFmpeg EN MEMORIA (1 por usuario)
# ============================================================

PROGRAM_HLS_PROCESSES = {}      # FFmpeg que genera HLS FINAL (NO se reinicia)
PROGRAM_FEEDER_PROCESSES = {}   # FFmpeg feeder (se mata y recrea al switchear cámara)


# ============================================================
# HLS MAESTRO (UNO POR USUARIO)
# ============================================================

def start_program_hls(user):

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

        # 🔧 FIX TIMESTAMPS: regenerar PTS/DTS y usar reloj de pared
        # Esto hace que el HLS maestro sea tolerante a saltos de timestamps
        # cuando el feeder cambia de fuente
        "-fflags", "+genpts+discardcorrupt",
        "-use_wallclock_as_timestamps", "1",

        "-i", f"rtmp://{RTMP_HOST}:{RTMP_PORT}/program_switch/{user.username}",

        "-c:v", "libx264",
        "-preset", "veryfast",
        "-tune", "zerolatency",
        "-pix_fmt", "yuv420p",
        "-r", "30",
        "-g", "60",
        "-keyint_min", "60",
        "-sc_threshold", "0",

        "-b:v", "2500k",
        "-maxrate", "2500k",
        "-bufsize", "5000k",

        "-c:a", "aac",
        "-b:a", "128k",
        "-ar", "44100",
        "-ac", "2",

        "-f", "hls",
        "-hls_time", "2",
        "-hls_list_size", "15",
        "-hls_flags", "delete_segments+program_date_time",
        "-hls_segment_filename", segments,
        playlist,
    ]

    print(f"[DEBUG] Iniciando HLS maestro para {user.username}")
    print("CMD HLS:", " ".join(cmd))

    # LOG A ARCHIVO para diagnóstico
    log_hls = open(f"/tmp/hls_maestro_{user.username}.log", "w")

    proc = subprocess.Popen(
        cmd,
        stdout=log_hls,
        stderr=log_hls,
        creationflags=subprocess.CREATE_NEW_PROCESS_GROUP if os.name == "nt" else 0
    )

    PROGRAM_HLS_PROCESSES[user.id] = proc


# ============================================================
# HELPER: matar proceso viejo con delay (en background)
# ============================================================

def _kill_after_delay(proc, delay_seconds, label="proceso"):
    """
    Mata un proceso FFmpeg después de un delay en un thread separado.
    Permite que el nuevo feeder se estabilice antes de cortar el viejo.
    """
    def _kill():
        print(f"[DEBUG] Esperando {delay_seconds}s antes de matar {label}...")
        time.sleep(delay_seconds)
        if proc.poll() is None:
            print(f"[DEBUG] Matando {label}")
            try:
                proc.terminate()
                proc.wait(timeout=5)
            except Exception:
                try:
                    proc.kill()
                except Exception:
                    pass
        else:
            print(f"[DEBUG] {label} ya había terminado solo")

    t = threading.Thread(target=_kill, daemon=True)
    t.start()


# ============================================================
# FEEDER (SWITCH DE CÁMARA)
# ============================================================

def switch_program_camera(user, stream_key):
    """
    Cambia la cámara EN VIVO sin cortar la transmisión.

    FIXES aplicados:
    1. -fflags +genpts + -use_wallclock_as_timestamps en el feeder:
       normaliza los timestamps de salida usando el reloj de pared,
       evitando el error "Non-monotonic DTS" que rompía el HLS maestro
       al recibir timestamps que retrocedían al cambiar de fuente.

    2. Overlap de 2 segundos: el nuevo feeder arranca primero y se
       estabiliza antes de matar el viejo, evitando que nginx-rtmp
       cierre el stream por falta de publisher.

    3. GOP reducido + force_key_frames: keyframe inmediato en el
       primer frame del nuevo feeder para transición más rápida.
    """

    old = PROGRAM_FEEDER_PROCESSES.get(user.id)

    FFMPEG_BIN = settings.FFMPEG_BIN_PATH
    RTMP_HOST = settings.RTMP_SERVER_HOST_INTERNAL
    RTMP_PORT = settings.RTMP_SERVER_PORT_INTERNAL

    input_rtmp = f"rtmp://{RTMP_HOST}:{RTMP_PORT}/live/{stream_key}"
    output_rtmp = f"rtmp://{RTMP_HOST}:{RTMP_PORT}/program_switch/{user.username}"

    feeder_cmd = [
        FFMPEG_BIN,

        # 🔧 FIX TIMESTAMPS: usar reloj de pared como base de timestamps
        # Esto garantiza que el nuevo feeder siempre emita timestamps
        # continuos y crecientes, sin importar desde dónde venía el stream
        "-fflags", "+genpts",
        "-use_wallclock_as_timestamps", "1",

        "-i", input_rtmp,

        "-c:v", "libx264",
        "-preset", "ultrafast",
        "-tune", "zerolatency",
        "-pix_fmt", "yuv420p",
        "-r", "30",
        "-g", "30",
        "-keyint_min", "30",
        "-sc_threshold", "0",
        "-force_key_frames", "expr:gte(t,0)",

        "-b:v", "2500k",
        "-maxrate", "2500k",
        "-bufsize", "5000k",

        "-c:a", "aac",
        "-b:a", "128k",
        "-ar", "44100",
        "-ac", "2",

        "-map", "0:v:0",
        "-map", "0:a:0",

        "-f", "flv",
        output_rtmp,
    ]

    print(f"[DEBUG] Arrancando NUEVO feeder → {stream_key}")
    print("CMD FEEDER:", " ".join(feeder_cmd))

    # LOG A ARCHIVO para diagnóstico (sobreescribe cada switch)
    log_feeder = open(f"/tmp/feeder_{user.username}.log", "w")

    # 1. Arrancar el NUEVO feeder primero
    new_feeder_proc = subprocess.Popen(
        feeder_cmd,
        stdout=log_feeder,
        stderr=log_feeder,
        creationflags=subprocess.CREATE_NEW_PROCESS_GROUP if os.name == "nt" else 0
    )

    # 2. Registrar el nuevo feeder inmediatamente
    PROGRAM_FEEDER_PROCESSES[user.id] = new_feeder_proc

    # 3. Matar el viejo con 2 segundos de delay (overlap)
    # 2s da tiempo al nuevo feeder de conectarse y estabilizar timestamps
    if old and old.poll() is None:
        print(f"[DEBUG] Feeder viejo será eliminado en 2s (overlap VPS)")
        _kill_after_delay(old, delay_seconds=2, label=f"feeder-viejo-{user.username}")
    else:
        print(f"[DEBUG] No había feeder viejo activo para {user.username}")


# ============================================================
# FIN REAL DEL EVENTO
# ============================================================

def stop_program_hls(user):

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

    print(f"[DEBUG] stop_program_hls completado para {user.username}")