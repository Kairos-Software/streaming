"""
Gestor SIMPLE de multistreaming
Toma el HLS de core y lo reenvía a plataformas externas
"""

import subprocess
import logging
import os
from datetime import datetime
from django.conf import settings
from multistream.models import CuentaYouTube, EstadoRetransmision
from core.models import CanalTransmision

logger = logging.getLogger(__name__)

# Diccionario en memoria: {user_id: {platform: proceso}}
RESTREAM_PROCESSES = {}


class StreamingManager:
    """
    Gestiona el reenvío del HLS a plataformas externas
    """

    def __init__(self, usuario):
        self.usuario = usuario

    def obtener_url_hls(self):
        """
        Obtiene la URL HLS del canal del usuario desde core
        """
        try:
            canal = CanalTransmision.objects.get(usuario=self.usuario)

            if not canal.en_vivo:
                return None

            if canal.url_hls:
                return canal.url_hls

            # Fallback manual
            hls_base = settings.HLS_BASE_URL
            return f"{hls_base}/program/{self.usuario.username}.m3u8"

        except CanalTransmision.DoesNotExist:
            logger.error(f"No existe canal para {self.usuario.username}")
            return None

    def iniciar_plataforma(self, platform):
        """
        Inicia retransmisión en una plataforma específica
        """
        try:
            # ==============================
            # CONFIGURACIÓN YOUTUBE
            # ==============================
            if platform == "youtube":
                cuenta = CuentaYouTube.objects.filter(
                    usuario=self.usuario,
                    activo=True
                ).first()

                if not cuenta:
                    return {"success": False, "message": "No hay cuenta de YouTube configurada"}

                if not cuenta.clave_transmision or not cuenta.url_ingestion:
                    return {"success": False, "message": "Configuración de YouTube incompleta"}

                url_destino = f"{cuenta.url_ingestion.rstrip('/')}/{cuenta.clave_transmision}"

            else:
                return {"success": False, "message": f"Plataforma {platform} no implementada"}

            # ==============================
            # ORIGEN HLS
            # ==============================
            url_hls = self.obtener_url_hls()
            if not url_hls:
                return {"success": False, "message": "No hay transmisión activa"}

            # ==============================
            # VALIDAR SI YA ESTÁ ACTIVA
            # ==============================
            estado_existente = EstadoRetransmision.objects.filter(
                usuario=self.usuario,
                plataforma=platform,
                detenido_en__isnull=True
            ).first()

            if estado_existente:
                return {"success": False, "message": f"{platform} ya está retransmitiendo"}

            # ==============================
            # INICIAR FFMPEG
            # ==============================
            proceso = self._iniciar_ffmpeg_youtube(url_hls, url_destino)

            # Guardar proceso en memoria
            RESTREAM_PROCESSES.setdefault(self.usuario.id, {})[platform] = proceso

            # Guardar estado BD
            EstadoRetransmision.objects.create(
                usuario=self.usuario,
                plataforma=platform,
                proceso_id=proceso.pid,
                estado="activo"
            )

            logger.info(f"✅ YouTube iniciado (PID {proceso.pid})")

            return {"success": True, "pid": proceso.pid}

        except Exception as e:
            logger.exception("Error iniciando retransmisión")
            EstadoRetransmision.objects.create(
                usuario=self.usuario,
                plataforma=platform,
                estado="error",
                mensaje_error=str(e),
                detenido_en=datetime.now()
            )
            return {"success": False, "message": str(e)}

    def detener_plataforma(self, platform):
        """
        Detiene retransmisión en una plataforma
        """
        try:
            proceso = RESTREAM_PROCESSES.get(self.usuario.id, {}).get(platform)

            estado = EstadoRetransmision.objects.filter(
                usuario=self.usuario,
                plataforma=platform,
                detenido_en__isnull=True
            ).first()

            if proceso and proceso.poll() is None:
                try:
                    proceso.terminate()
                    proceso.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    proceso.kill()

            # Limpiar memoria
            RESTREAM_PROCESSES.get(self.usuario.id, {}).pop(platform, None)

            if estado:
                estado.estado = "detenido"
                estado.detenido_en = datetime.now()
                estado.save()

            logger.info(f"🛑 Retransmisión detenida: {platform}")
            return {"success": True}

        except Exception as e:
            logger.exception("Error deteniendo retransmisión")
            return {"success": False, "message": str(e)}

    # =====================================================
    # FFMPEG YOUTUBE (HLS → RTMP)
    # =====================================================
    def _iniciar_ffmpeg_youtube(self, url_hls, url_rtmp):
        """
        Retransmisión compatible con YouTube
        """

        ffmpeg_bin = settings.FFMPEG_BIN_PATH

        comando = [
            ffmpeg_bin,

            # Input
            "-i", url_hls,

            # Video (YouTube-safe)
            "-c:v", "libx264",
            "-preset", "veryfast",
            "-tune", "zerolatency",
            "-profile:v", "high",
            "-level", "4.2",
            "-pix_fmt", "yuv420p",
            "-g", "60",
            "-keyint_min", "60",
            "-sc_threshold", "0",

            # Audio
            "-c:a", "aac",
            "-b:a", "128k",

            # Output
            "-f", "flv",
            "-flvflags", "no_duration_filesize",

            url_rtmp
        ]

        logger.info("🚀 FFmpeg YouTube:\n" + " ".join(comando))

        return subprocess.Popen(
            comando,
            stdin=subprocess.DEVNULL,
            stdout=None,
            stderr=None,
            creationflags=subprocess.CREATE_NEW_PROCESS_GROUP if os.name == "nt" else 0
        )

    @staticmethod
    def limpiar_procesos_huerfanos():
        """
        Elimina procesos FFmpeg muertos
        """
        for user_id in list(RESTREAM_PROCESSES.keys()):
            for platform in list(RESTREAM_PROCESSES[user_id].keys()):
                proceso = RESTREAM_PROCESSES[user_id][platform]
                if proceso.poll() is not None:
                    logger.warning(f"⚠️ Proceso huérfano: {user_id} {platform}")
                    RESTREAM_PROCESSES[user_id].pop(platform)

            if not RESTREAM_PROCESSES[user_id]:
                del RESTREAM_PROCESSES[user_id]
