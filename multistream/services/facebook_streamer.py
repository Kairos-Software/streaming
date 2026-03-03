"""
FACEBOOK STREAMER - V_HLS_STABLE
Lee del HLS maestro (igual que tu plataforma)
El HLS maestro genera chunks continuos sin importar los cambios de cámara
"""
import os
import logging
from django.conf import settings
from multistream.models import CuentaFacebook
from .base_streamer import BaseStreamer

logger = logging.getLogger(__name__)


class FacebookStreamer(BaseStreamer):

    PLATFORM_NAME = 'facebook'

    def validate_account_credentials(self):
        try:
            cuenta = CuentaFacebook.objects.get(usuario=self.user, activo=True)
            if not cuenta.clave_transmision:
                raise ValueError("Falta clave de transmisión de Facebook")
            if not cuenta.url_ingestion:
                raise ValueError("Falta URL de ingestión de Facebook")
            logger.info(f"[FACEBOOK] Credenciales OK para {self.user.username}")
        except CuentaFacebook.DoesNotExist:
            raise ValueError(f"No existe cuenta de Facebook para {self.user.username}")

    def get_rtmp_destination_url(self):
        cuenta = CuentaFacebook.objects.get(usuario=self.user, activo=True)
        url = f"rtmp://127.0.0.1:19350/rtmp/{cuenta.clave_transmision}"
        logger.info(f"[FACEBOOK] Destino via stunnel → rtmp://127.0.0.1:19350/rtmp/****")
        return url

    def build_ffmpeg_command(self, destination_url):
        ffmpeg_path = settings.FFMPEG_BIN_PATH
        
        # ========== LEE DEL HLS MAESTRO (como tu plataforma) ==========
        port = os.getenv('HLS_INTERNAL_PORT', '8080')
        hls_source = f"http://127.0.0.1:{port}/hls/program/{self.user.username}.m3u8"
        
        logger.info(f"[FACEBOOK] Source HLS: {hls_source}")

        command = [
            ffmpeg_path,
            # ========== INPUT (HLS) ==========
            '-fflags', '+genpts+discardcorrupt',
            '-live_start_index', '-1',
            '-i', hls_source,
            # ========== VIDEO (COPY) ==========
            '-c:v', 'copy',
            # ========== AUDIO (COPY) ==========
            '-c:a', 'copy',
            # ========== OUTPUT ==========
            '-f', 'flv',
            '-flvflags', 'no_duration_filesize',
            destination_url
        ]

        logger.info(f"[FACEBOOK] Comando listo → HLS copy → stunnel → Facebook")
        return command
