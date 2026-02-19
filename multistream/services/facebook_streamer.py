"""
FACEBOOK STREAMER - V4 ULTRA ESTABLE
Configuración ultra conservadora para evitar desconexiones a los 5 minutos.

CAMBIOS CRÍTICOS:
- Bitrate MÁS BAJO y ultra estable (2500k CBR)
- FPS forzado a 25 constante
- Keyframes cada 2 segundos EXACTOS
- Buffer más grande para absorber fluctuaciones
- Preset ultrafast (máxima velocidad)
- Sin force_key_frames (puede causar problemas)
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
        Comando ULTRA CONSERVADOR para Facebook.
        
        OBJETIVO: Transmisión estable por HORAS sin desconexiones.
        
        CAMBIOS VS V3:
        - Bitrate reducido: 2500k (más estable)
        - Preset: ultrafast (era superfast)
        - Sin force_key_frames (causaba problemas)
        - FPS: -r 25 ANTES del input (más estable)
        - Buffer más grande: 10000k
        - vsync cfr (constant frame rate)
        """
        logger.info("[FFMPEG] Construyendo comando ULTRA CONSERVADOR")
        logger.info("-" * 80)
        
        ffmpeg_path = settings.FFMPEG_BIN_PATH
        rtmp_host = getattr(settings, 'RTMP_SERVER_HOST_INTERNAL', '127.0.0.1')
        rtmp_port = getattr(settings, 'RTMP_SERVER_PORT_INTERNAL', '9000')
        rtmp_source = f"rtmp://{rtmp_host}:{rtmp_port}/program_switch/{self.user.username}"
        
        logger.info(f"[SOURCE] {rtmp_source}")
        logger.info(f"[DEST] {destination_url[:60]}...****")
        
        # ==========================================
        # COMANDO ULTRA CONSERVADOR
        # ==========================================
        command = [
            ffmpeg_path,
            
            # ==========================================
            # INPUT - Con FPS forzado ANTES de leer
            # ==========================================
            '-re',              # 🔧 NUEVO: Read input at native frame rate
            '-i', rtmp_source,
            
            # ==========================================
            # VIDEO - Ultra conservador
            # ==========================================
            '-c:v', 'libx264',
            
            # 🔧 CRÍTICO: ultrafast (máxima velocidad)
            '-preset', 'ultrafast',
            
            '-tune', 'zerolatency',
            '-pix_fmt', 'yuv420p',
            
            # ==========================================
            # BITRATE - MÁS BAJO para estabilidad
            # ==========================================
            '-b:v', '2500k',        # 🔧 Reducido de 3000k
            '-maxrate', '2500k',    # 🔧 CBR perfecto
            '-minrate', '2500k',    # 🔧 CBR perfecto
            '-bufsize', '10000k',   # 🔧 Buffer MÁS GRANDE (era 6000k)
            
            # ==========================================
            # KEYFRAMES - Cada 2 segundos EXACTOS
            # ==========================================
            '-g', '50',             # 50 frames a 25fps = 2 segundos
            '-keyint_min', '50',    # Mínimo = máximo
            '-sc_threshold', '0',   # Desactiva scene detection
            # 🔧 SIN force_key_frames (puede causar problemas)
            
            # ==========================================
            # FRAMERATE - CRÍTICO
            # ==========================================
            '-r', '25',             # Output FPS
            '-vsync', 'cfr',        # 🔧 NUEVO: Constant Frame Rate
            
            # ==========================================
            # AUDIO - Copy
            # ==========================================
            '-c:a', 'copy',
            
            # ==========================================
            # THREADING
            # ==========================================
            '-threads', '2',
            
            # ==========================================
            # OUTPUT - Con opciones adicionales
            # ==========================================
            '-f', 'flv',
            '-flvflags', 'no_duration_filesize',  # 🔧 NUEVO: Evita metadata problems
            
            destination_url
        ]
        
        logger.info("[OK] Comando ULTRA CONSERVADOR:")
        logger.info("  ✅ Preset: ultrafast (máxima velocidad)")
        logger.info("  ✅ Bitrate: 2500k CBR (ultra estable)")
        logger.info("  ✅ FPS: 25 con vsync cfr (frame rate constante)")
        logger.info("  ✅ Keyframes: cada 2 seg exactos")
        logger.info("  ✅ Buffer: 10000k (grande para absorber fluctuaciones)")
        logger.info("  ✅ -re: lectura a velocidad nativa")
        logger.info("")
        logger.info("OBJETIVO: Transmisión ESTABLE por 1+ hora sin cortes")
        logger.info("-" * 80)
        
        return command