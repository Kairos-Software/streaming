"""
RADIO MANAGER
=============
Modo radio: video con imagen estática + audio RTMP live.

La imagen se lee desde canal.get_imagen_radio() — cada usuario
tiene su propia imagen configurada desde Ajustes > Perfil.

Pipeline:
  [imagen usuario loop] ──┐
                           ├──► feeder → /program_switch/username → HLS maestro
  [audio RTMP live]    ──┘
"""

import os
import tempfile
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
    hacia /program_switch.

    La imagen se lee desde CanalTransmision.get_imagen_radio()
    que devuelve radio_imagen_path del usuario o el fallback de settings.
    """
    from core.models import CanalTransmision

    FFMPEG_BIN = settings.FFMPEG_BIN_PATH
    RTMP_HOST  = settings.RTMP_SERVER_HOST_INTERNAL
    RTMP_PORT  = settings.RTMP_SERVER_PORT_INTERNAL

    canal = CanalTransmision.objects.filter(usuario=user).first()
    imagen_path = canal.get_imagen_radio() if canal else ""

    if not imagen_path:
        raise ValueError(
            "[RADIO] No tenés imagen de radio configurada. "
            "Andá a Ajustes > Perfil para subirla."
        )

    if not os.path.isfile(imagen_path):
        raise FileNotFoundError(
            f"[RADIO] Imagen no encontrada en disco: {imagen_path}. "
            f"Volvé a subir la imagen desde Ajustes > Perfil."
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
        # ── Video: escalar a 1280x720 con letterbox ──────────────────
        "-vf", "scale=1280:720:force_original_aspect_ratio=decrease,pad=1280:720:(ow-iw)/2:(oh-ih)/2:black",
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
        # ── Audio: resync para evitar disco rayado ───────────────────
        "-c:a", "aac",
        "-af", "aresample=async=1000",
        "-b:a", "128k",
        "-ar", "44100",
        "-ac", "2",
        # ── Salida RTMP ─────────────────────────────────────────────
        "-f", "flv",
        output_rtmp,
    ]

    old = RADIO_FEEDER_PROCESSES.get(user.id)

    log_path = os.path.join(tempfile.gettempdir(), f"radio_feeder_{user.username}.log")
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