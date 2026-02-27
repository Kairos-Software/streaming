"""
RADIO MANAGER
=============
Modo radio: video con imagen estática + audio RTMP live.

La imagen se configura via variable de entorno RADIO_IMAGE_PATH
en .env.local o .env.production según el entorno.

Pipeline:
  [imagen.jpg loop] ──┐
                       ├──► feeder → /program_switch/username → HLS maestro
  [audio RTMP live] ──┘

Las plataformas externas (YouTube, Facebook, etc.) ven la imagen + audio.
El reproductor público puede mostrar la misma imagen o su propio overlay.
"""

import os
import subprocess
import time
import threading
import logging
from django.conf import settings

logger = logging.getLogger(__name__)

RADIO_FEEDER_PROCESSES = {}


def _kill_after_delay(proc, delay_seconds, label="proceso-radio"):
    def _do_kill():
        time.sleep(delay_seconds)
        if proc.poll() is None:
            try:
                proc.terminate()
                proc.wait(timeout=5)
            except Exception:
                try:
                    proc.kill()
                except Exception:
                    pass

    t = threading.Thread(target=_do_kill, daemon=True)
    t.start()


def start_radio_feeder(user, stream_key):
    """
    Lanza un feeder FFmpeg con imagen estática + audio RTMP
    hacia /program_switch. La imagen se lee desde RADIO_IMAGE_PATH.

    Plataformas externas (YouTube, Facebook) ven imagen + audio real.
    """
    FFMPEG_BIN  = settings.FFMPEG_BIN_PATH
    RTMP_HOST   = settings.RTMP_SERVER_HOST_INTERNAL
    RTMP_PORT   = settings.RTMP_SERVER_PORT_INTERNAL
    imagen_path = settings.RADIO_IMAGE_PATH

    if not imagen_path:
        raise ValueError("[RADIO] RADIO_IMAGE_PATH no está configurado en settings.")

    if not os.path.isfile(imagen_path):
        raise FileNotFoundError(
            f"[RADIO] Imagen no encontrada: {imagen_path}. "
            f"Configurá RADIO_IMAGE_PATH en tu .env.local o .env.production"
        )

    input_rtmp  = f"rtmp://{RTMP_HOST}:{RTMP_PORT}/live/{stream_key}"
    output_rtmp = f"rtmp://{RTMP_HOST}:{RTMP_PORT}/program_switch/{user.username}"

    cmd = [
        FFMPEG_BIN,
        # ── Fuente 1: imagen estática en loop ───────────────────────
        "-loop", "1",
        "-framerate", "25",
        "-i", imagen_path,
        # ── Fuente 2: RTMP live (solo audio) ────────────────────────
        "-fflags", "+genpts",
        "-use_wallclock_as_timestamps", "1",
        "-i", input_rtmp,
        # ── Mapeo: video de [0], audio de [1] ───────────────────────
        "-map", "0:v",
        "-map", "1:a",
        # ── Video: H.264 con imagen estática ────────────────────────
        "-c:v", "libx264",
        "-preset", "ultrafast",
        "-tune", "stillimage",
        "-pix_fmt", "yuv420p",
        "-r", "25",
        "-g", "50",
        "-keyint_min", "50",
        "-sc_threshold", "0",
        "-b:v", "300k",
        "-maxrate", "300k",
        "-bufsize", "600k",
        # ── Audio: igual que feeder de video ────────────────────────
        "-c:a", "aac",
        "-b:a", "128k",
        "-ar", "44100",
        "-ac", "2",
        # ── Salida RTMP ─────────────────────────────────────────────
        "-f", "flv",
        output_rtmp,
    ]

    old = RADIO_FEEDER_PROCESSES.get(user.id)

    log_path = f"/tmp/radio_feeder_{user.username}.log"
    logger.info(f"[RADIO] Iniciando feeder radio para {user.username} | imagen={imagen_path}")

    log_file = open(log_path, "w")
    new_proc = subprocess.Popen(
        cmd,
        stdout=log_file,
        stderr=log_file,
        creationflags=subprocess.CREATE_NEW_PROCESS_GROUP if os.name == "nt" else 0,
    )
    RADIO_FEEDER_PROCESSES[user.id] = new_proc

    if old and old.poll() is None:
        _kill_after_delay(old, delay_seconds=2, label=f"radio-feeder-viejo-{user.username}")

    return new_proc


def stop_radio_feeder(user):
    proc = RADIO_FEEDER_PROCESSES.pop(user.id, None)
    if proc and proc.poll() is None:
        logger.info(f"[RADIO] Deteniendo feeder radio para {user.username}")
        try:
            proc.terminate()
            proc.wait(timeout=5)
        except Exception as e:
            logger.warning(f"[RADIO] Error al terminar feeder radio: {e}")
            try:
                proc.kill()
            except Exception:
                pass


def is_radio_feeder_active(user):
    proc = RADIO_FEEDER_PROCESSES.get(user.id)
    return proc is not None and proc.poll() is None