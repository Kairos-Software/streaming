"""
FFMPEG MANAGER - V_SWITCH_STABLE_720P

✔ Cambio de cámara estable (sin congelamientos aleatorios)
✔ Audio limpio
✔ 720p buena calidad
✔ HLS maestro en COPY (sin doble encode)
✔ Aguanta muchos switches seguidos
✔ Optimizado para VPS 1 núcleo / 4GB RAM
"""

import os
import subprocess
import time
import threading
from django.conf import settings

PROGRAM_HLS_PROCESSES = {}
PROGRAM_FEEDER_PROCESSES = {}


# ============================================================
# HLS MAESTRO (SOLO COPY - MUY ESTABLE)
# ============================================================

def start_program_hls(user):

    if user.id in PROGRAM_HLS_PROCESSES:
        proc = PROGRAM_HLS_PROCESSES[user.id]
        if proc.poll() is None:
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
        "-fflags", "+genpts+discardcorrupt",
        "-use_wallclock_as_timestamps", "1",
        "-i", f"rtmp://{RTMP_HOST}:{RTMP_PORT}/program_switch/{user.username}",
        "-c", "copy",
        "-f", "hls",
        "-hls_time", "2",
        "-hls_list_size", "10",
        "-hls_flags", "delete_segments+program_date_time+independent_segments",
        "-hls_segment_filename", segments,
        playlist,
    ]

    log = open(f"/tmp/hls_{user.username}.log", "w")
    proc = subprocess.Popen(cmd, stdout=log, stderr=log)
    PROGRAM_HLS_PROCESSES[user.id] = proc


# ============================================================
# KILL CON OVERLAP
# ============================================================

def _kill_after_delay(proc, delay):
    def kill():
        time.sleep(delay)
        if proc.poll() is None:
            try:
                proc.terminate()
                proc.wait(timeout=5)
            except Exception:
                proc.kill()
    threading.Thread(target=kill, daemon=True).start()


# ============================================================
# SWITCH DE CÁMARA (ENCODE DEFINITIVO 720P ESTABLE)
# ============================================================

def switch_program_camera(user, stream_key):

    old = PROGRAM_FEEDER_PROCESSES.get(user.id)

    FFMPEG_BIN = settings.FFMPEG_BIN_PATH
    RTMP_HOST = settings.RTMP_SERVER_HOST_INTERNAL
    RTMP_PORT = settings.RTMP_SERVER_PORT_INTERNAL

    input_rtmp = f"rtmp://{RTMP_HOST}:{RTMP_PORT}/live/{stream_key}"
    output_rtmp = f"rtmp://{RTMP_HOST}:{RTMP_PORT}/program_switch/{user.username}"

    letterbox = (
        "scale=1280:720:force_original_aspect_ratio=decrease,"
        "pad=1280:720:(ow-iw)/2:(oh-ih)/2:black"
    )

    cmd = [
        FFMPEG_BIN,

        "-fflags", "+genpts",
        "-use_wallclock_as_timestamps", "1",
        "-i", input_rtmp,

        # ================= VIDEO =================
        "-vf", letterbox,
        "-c:v", "libx264",
        "-preset", "veryfast",
        "-profile:v", "high",
        "-level", "4.1",
        "-tune", "zerolatency",
        "-pix_fmt", "yuv420p",
        "-r", "30",

        # 🔥 CLAVE PARA ESTABILIDAD DE SWITCH
        "-g", "30",
        "-keyint_min", "30",
        "-sc_threshold", "0",
        "-force_key_frames", "expr:gte(t,0)",

        # Calidad real 720p
        "-b:v", "4200k",
        "-maxrate", "4500k",
        "-bufsize", "9000k",

        # ================= AUDIO =================
        "-c:a", "aac",
        "-b:a", "128k",
        "-ar", "44100",
        "-ac", "2",
        "-af", "aresample=async=1:first_pts=0",

        "-map", "0:v:0",
        "-map", "0:a:0",

        "-f", "flv",
        output_rtmp,
    ]

    log = open(f"/tmp/feeder_{user.username}.log", "w")
    proc = subprocess.Popen(cmd, stdout=log, stderr=log)

    PROGRAM_FEEDER_PROCESSES[user.id] = proc

    # Overlap 2 segundos para switch suave
    if old and old.poll() is None:
        _kill_after_delay(old, 2)


# ============================================================
# STOP
# ============================================================

def stop_program_hls(user):

    feeder = PROGRAM_FEEDER_PROCESSES.get(user.id)
    if feeder and feeder.poll() is None:
        feeder.terminate()

    hls = PROGRAM_HLS_PROCESSES.get(user.id)
    if hls and hls.poll() is None:
        hls.terminate()

    PROGRAM_FEEDER_PROCESSES.pop(user.id, None)
    PROGRAM_HLS_PROCESSES.pop(user.id, None)