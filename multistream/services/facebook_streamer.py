"""
FACEBOOK STREAMER
Gestiona la retransmisión específica a Facebook Live.
"""

import logging
from django.conf import settings
from multistream.models import CuentaFacebook
from .base_streamer import BaseStreamer

logger = logging.getLogger(__name__)


class FacebookStreamer(BaseStreamer):
    """
    Implementación específica para retransmisión a Facebook Live.
    
    Requisitos de Facebook:
    - Codec de video: H.264
    - Codec de audio: AAC
    - Formato: FLV
    - Protocolo: RTMP/RTMPS (puerto 443 para RTMPS)
    """
    
    PLATFORM_NAME = 'facebook'
    
    def get_rtmp_destination_url(self):
        """
        Construye la URL RTMP/RTMPS de Facebook.
        
        Formato: {url_ingestion}/{clave_transmision}
        Ejemplo: rtmps://live-api-s.facebook.com:443/rtmp/xxxx-xxxx-xxxx-xxxx
        
        Returns:
            str: URL RTMP/RTMPS completa de Facebook
        
        Raises:
            ValueError: Si no hay cuenta de Facebook configurada
        """
        try:
            cuenta = CuentaFacebook.objects.get(
                usuario=self.user,
                activo=True
            )
            
            if not cuenta.clave_transmision:
                raise ValueError("La cuenta de Facebook no tiene clave de transmisión configurada")
            
            if not cuenta.url_ingestion:
                raise ValueError("La cuenta de Facebook no tiene URL de ingestión configurada")
            
            # Construir URL final
            url_base = cuenta.url_ingestion.rstrip('/')
            url_completa = f"{url_base}/{cuenta.clave_transmision}"
            
            logger.info(f"🔗 URL destino Facebook: {url_base}/****")
            
            return url_completa
            
        except CuentaFacebook.DoesNotExist:
            raise ValueError(f"No existe cuenta de Facebook para el usuario {self.user.username}")
    
    def validate_account_credentials(self):
        """
        Valida que el usuario tenga una cuenta de Facebook activa y configurada.
        
        Raises:
            ValueError: Si no hay cuenta o está mal configurada
        """
        try:
            cuenta = CuentaFacebook.objects.get(
                usuario=self.user,
                activo=True
            )
            
            if not cuenta.clave_transmision:
                raise ValueError("Falta configurar la clave de transmisión de Facebook")
            
            if not cuenta.url_ingestion:
                raise ValueError("Falta configurar la URL de ingestión de Facebook")
            
            logger.info(f"✅ Credenciales de Facebook válidas para {self.user.username}")
            
        except CuentaFacebook.DoesNotExist:
            raise ValueError(
                f"No existe cuenta de Facebook activa para {self.user.username}. "
                f"Configure sus credenciales en Ajustes > Retransmisión."
            )
    
    def build_ffmpeg_command(self, destination_url):
        """
        Construye el comando FFmpeg optimizado para Facebook Live.
        
        Lee RTMP interno (program_switch) y lo reenvía a Facebook.
        
        Nota: Facebook Live puede usar RTMPS (puerto 443) para mejor compatibilidad
        con firewalls corporativos.
        
        Args:
            destination_url (str): URL RTMP/RTMPS de Facebook
        
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
            # OUTPUT - FLV para RTMP/RTMPS
            # ==========================================
            '-f', 'flv',
            
            destination_url
        ]
        
        logger.info(f"🔧 Comando FFmpeg Facebook (copy mode - sin recodificar)")
        logger.info(f"   {' '.join(command)}")
        
        return command