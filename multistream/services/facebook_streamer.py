"""
FACEBOOK STREAMER - VERSION CON ASPECT RATIO CORRECTO
Preserva la orientación original (horizontal o vertical)
"""

import logging
from django.conf import settings
from multistream.models import CuentaFacebook
from .base_streamer import BaseStreamer

logger = logging.getLogger(__name__)


class FacebookStreamer(BaseStreamer):
    
    PLATFORM_NAME = 'facebook'
    
    def validate_account_credentials(self):
        logger.info("=" * 80)
        logger.info("[FACEBOOK] Validando credenciales")
        logger.info("=" * 80)
        
        try:
            cuenta = CuentaFacebook.objects.get(usuario=self.user, activo=True)
            
            if not cuenta.clave_transmision:
                raise ValueError("Falta clave de transmisión de Facebook")
            if not cuenta.url_ingestion:
                raise ValueError("Falta URL de ingestión de Facebook")
            
            logger.info(f"[OK] Usuario: {self.user.username}")
            logger.info(f"  - Clave: {cuenta.clave_transmision[:10]}...{cuenta.clave_transmision[-4:]}")
            logger.info(f"  - URL: {cuenta.url_ingestion}")
            logger.info("=" * 80)
            
        except CuentaFacebook.DoesNotExist:
            raise ValueError(f"No existe cuenta de Facebook para {self.user.username}")
    
    def get_rtmp_destination_url(self):
        logger.info("[FACEBOOK] Construyendo URL")
        logger.info("-" * 80)
        
        cuenta = CuentaFacebook.objects.get(usuario=self.user, activo=True)
        url_base = cuenta.url_ingestion.rstrip('/')
        
        logger.info(f"[CONFIG] URL original: {url_base}")
        
        # Asegurar RTMPS
        if url_base.startswith('rtmp://'):
            url_base = url_base.replace('rtmp://', 'rtmps://')
            if ':443' not in url_base and 'facebook.com' in url_base:
                url_base = url_base.replace('facebook.com', 'facebook.com:443')
            logger.info(f"[FIX] Convertido a RTMPS: {url_base}")
        
        elif url_base.startswith('rtmps://'):
            if ':443' not in url_base and 'facebook.com' in url_base:
                url_base = url_base.replace('facebook.com', 'facebook.com:443')
                logger.info(f"[FIX] Puerto 443 agregado")
            logger.info("[OK] Ya usa RTMPS")
        
        else:
            url_base = f"rtmps://{url_base}"
            if ':443' not in url_base and 'facebook.com' in url_base:
                url_base = url_base.replace('facebook.com', 'facebook.com:443')
        
        # Asegurar /rtmp
        if '/rtmp' not in url_base:
            url_base = f"{url_base}/rtmp"
        
        url_completa = f"{url_base}/{cuenta.clave_transmision}"
        
        key_preview = f"{cuenta.clave_transmision[:8]}...{cuenta.clave_transmision[-4:]}"
        logger.info(f"[DESTINO] {url_base}/{key_preview}")
        logger.info(f"[PROTOCOLO] RTMPS:443")
        logger.info("-" * 80)
        
        return url_completa
    
    def build_ffmpeg_command(self, destination_url):
        """
        Comando optimizado que PRESERVA aspect ratio original.
        
        CRITICO: No fuerza resolución, respeta la del source
        """
        logger.info("[FFMPEG] Construyendo comando")
        logger.info("-" * 80)
        
        ffmpeg_path = settings.FFMPEG_BIN_PATH
        rtmp_host = getattr(settings, 'RTMP_SERVER_HOST_INTERNAL', '127.0.0.1')
        rtmp_port = getattr(settings, 'RTMP_SERVER_PORT_INTERNAL', '9000')
        rtmp_source = f"rtmp://{rtmp_host}:{rtmp_port}/program_switch/{self.user.username}"
        
        logger.info(f"[SOURCE] {rtmp_source}")
        logger.info(f"[DEST] {destination_url[:60]}...****")
        
        # ==========================================
        # COMANDO OPTIMIZADO
        # ==========================================
        command = [
            ffmpeg_path,
            
            # INPUT
            '-i', rtmp_source,
            
            # ==========================================
            # VIDEO - Recodificar SIN cambiar resolución
            # ==========================================
            '-c:v', 'libx264',
            
            # PRESET
            '-preset', 'veryfast',
            
            # TUNE
            '-tune', 'zerolatency',
            
            # PIXEL FORMAT
            '-pix_fmt', 'yuv420p',
            
            # BITRATE - MAS ALTO para horizontal
            '-b:v', '4000k',
            '-maxrate', '4000k',
            '-bufsize', '8000k',
            
            # KEYFRAME INTERVAL
            '-g', '60',
            '-keyint_min', '60',
            '-sc_threshold', '0',
            
            # FRAMERATE
            '-r', '30',
            
            # ==========================================
            # CRITICO: NO forzar resolución
            # Esto permite que horizontal sea horizontal
            # y vertical sea vertical
            # ==========================================
            # NO incluir -s (scale)
            # NO incluir -vf scale
            # Dejar que FFmpeg use la resolución original
            
            # ==========================================
            # AUDIO
            # ==========================================
            '-c:a', 'copy',
            
            # ==========================================
            # OUTPUT
            # ==========================================
            '-f', 'flv',
            
            destination_url
        ]
        
        logger.info("[OK] Comando OPTIMIZADO:")
        logger.info("  - Video: H.264 con aspect ratio ORIGINAL")
        logger.info("  - Bitrate: 4000k (calidad alta)")
        logger.info("  - Resolucion: SIN FORZAR (respeta source)")
        logger.info("  - Horizontal: se mantiene horizontal")
        logger.info("  - Vertical: se mantiene vertical")
        logger.info("-" * 80)
        logger.info("")
        logger.info("IMPORTANTE:")
        logger.info("  - Si ManyCam envia 1920x1080 -> Facebook recibe 1920x1080")
        logger.info("  - Si ManyCam envia 720x1280 -> Facebook recibe 720x1280")
        logger.info("  - Sin cortes, sin zoom forzado")
        logger.info("")
        
        return command