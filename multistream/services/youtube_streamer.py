"""
YOUTUBE STREAMER
Gestiona la retransmisión específica a YouTube Live.
"""

import logging
from django.conf import settings
from multistream.models import CuentaYouTube
from .base_streamer import BaseStreamer

logger = logging.getLogger(__name__)


class YouTubeStreamer(BaseStreamer):
    """
    Implementación específica para retransmisión a YouTube Live.
    
    Requisitos de YouTube:
    - Codec de video: H.264
    - Codec de audio: AAC
    - Formato: FLV
    - Protocolo: RTMP
    """
    
    PLATFORM_NAME = 'youtube'
    
    def get_rtmp_destination_url(self):
        """
        Construye la URL RTMP de YouTube.
        
        Formato: {url_ingestion}/{clave_transmision}
        Ejemplo: rtmp://a.rtmp.youtube.com/live2/xxxx-xxxx-xxxx-xxxx
        
        Returns:
            str: URL RTMP completa de YouTube
        
        Raises:
            ValueError: Si no hay cuenta de YouTube configurada
        """
        try:
            cuenta = CuentaYouTube.objects.get(
                usuario=self.user,
                activo=True
            )
            
            if not cuenta.clave_transmision:
                raise ValueError("La cuenta de YouTube no tiene clave de transmisión configurada")
            
            if not cuenta.url_ingestion:
                raise ValueError("La cuenta de YouTube no tiene URL de ingestión configurada")
            
            # Construir URL final
            url_base = cuenta.url_ingestion.rstrip('/')
            url_completa = f"{url_base}/{cuenta.clave_transmision}"
            
            logger.info(f"🔗 URL destino YouTube: {url_base}/****")
            
            return url_completa
            
        except CuentaYouTube.DoesNotExist:
            raise ValueError(f"No existe cuenta de YouTube para el usuario {self.user.username}")
    
    def validate_account_credentials(self):
        """
        Valida que el usuario tenga una cuenta de YouTube activa y configurada.
        
        Raises:
            ValueError: Si no hay cuenta o está mal configurada
        """
        try:
            cuenta = CuentaYouTube.objects.get(
                usuario=self.user,
                activo=True
            )
            
            if not cuenta.clave_transmision:
                raise ValueError("Falta configurar la clave de transmisión de YouTube")
            
            if not cuenta.url_ingestion:
                raise ValueError("Falta configurar la URL de ingestión de YouTube")
            
            logger.info(f"✅ Credenciales de YouTube válidas para {self.user.username}")
            
        except CuentaYouTube.DoesNotExist:
            raise ValueError(
                f"No existe cuenta de YouTube activa para {self.user.username}. "
                f"Configure sus credenciales en Ajustes > Retransmisión."
            )
    
    def build_ffmpeg_command(self, destination_url):
        """
        Construye el comando FFmpeg optimizado para YouTube Live.
        
        Lee RTMP interno (program_switch) y lo reenvía a YouTube.
        Esto evita problemas con segmentos HLS eliminados.
        
        Args:
            destination_url (str): URL RTMP de YouTube
        
        Returns:
            list: Comando FFmpeg completo
        """
        ffmpeg_path = settings.FFMPEG_BIN_PATH
        
        # Construir URL RTMP interna (program_switch)
        rtmp_host = getattr(settings, 'RTMP_SERVER_HOST_INTERNAL', '127.0.0.1')
        rtmp_port = getattr(settings, 'RTMP_SERVER_PORT_INTERNAL', '9000')
        
        # El stream en program_switch se llama igual que el username
        rtmp_source = f"rtmp://{rtmp_host}:{rtmp_port}/program_switch/{self.user.username}"
        
        logger.info(f"📡 RTMP fuente: {rtmp_source}")
        logger.info(f"📡 RTMP destino: {destination_url[:50]}...****")
        
        command = [
            ffmpeg_path,
            
            # ==========================================
            # INPUT (RTMP program_switch)
            # ==========================================
            '-i', rtmp_source,
            
            # ==========================================
            # VIDEO - Copy sin recodificar (más eficiente)
            # ==========================================
            '-c:v', 'copy',
            
            # ==========================================
            # AUDIO - Copy sin recodificar
            # ==========================================
            '-c:a', 'copy',
            
            # ==========================================
            # OUTPUT - FLV para RTMP
            # ==========================================
            '-f', 'flv',
            
            destination_url
        ]
        
        logger.info(f"🔧 Comando FFmpeg (copy mode - sin recodificar)")
        logger.info(f"   {' '.join(command)}")
        
        return command