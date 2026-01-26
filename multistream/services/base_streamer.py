"""
BASE STREAMER - Clase abstracta base para todas las plataformas

Esta es la "plantilla" que todas las plataformas deben seguir.
Define QUÉ métodos debe tener cada plataforma, pero no CÓMO implementarlos.
"""

from abc import ABC, abstractmethod
import subprocess
import logging

logger = logging.getLogger(__name__)


class BaseStreamer(ABC):
    """
    Clase base abstracta para gestionar transmisiones a plataformas externas.
    
    Toda plataforma (YouTube, Facebook, Twitch, etc.) debe heredar de esta clase
    e implementar los métodos abstractos.
    """
    
    # Nombre de la plataforma (ej: "youtube", "facebook")
    PLATFORM_NAME = None
    
    def __init__(self, user, source_url):
        """
        Constructor base.
        
        Args:
            user: Usuario de Django que inicia la transmisión
            source_url: URL HLS de origen (ej: http://servidor/stream.m3u8)
        """
        self.user = user
        self.source_url = source_url
        self.process = None  # Proceso FFmpeg (se crea al iniciar)
    
    # =========================================
    # MÉTODOS ABSTRACTOS (obligatorios)
    # Cada plataforma DEBE implementar estos
    # =========================================
    
    @abstractmethod
    def get_rtmp_destination_url(self):
        """
        Construye la URL RTMP de destino de la plataforma.
        
        Ejemplo YouTube: rtmp://a.rtmp.youtube.com/live2/{stream_key}
        Ejemplo Facebook: rtmps://live-api-s.facebook.com:443/rtmp/{stream_key}
        
        Returns:
            str: URL RTMP completa
        
        Raises:
            ValueError: Si no hay credenciales configuradas
        """
        pass
    
    @abstractmethod
    def build_ffmpeg_command(self, destination_url):
        """
        Construye el comando FFmpeg específico de la plataforma.
        
        Cada plataforma tiene requisitos diferentes:
        - YouTube: acepta H.264 con ciertos parámetros
        - Facebook: puede requerir diferentes codecs o bitrates
        
        Args:
            destination_url (str): URL RTMP de destino
        
        Returns:
            list: Lista con el comando FFmpeg (ej: ['ffmpeg', '-i', '...'])
        """
        pass
    
    @abstractmethod
    def validate_account_credentials(self):
        """
        Valida que el usuario tenga credenciales configuradas para esta plataforma.
        
        Ejemplo:
            - YouTube: verificar que existe CuentaYouTube con clave activa
            - Facebook: verificar que existe CuentaFacebook con token válido
        
        Raises:
            ValueError: Si no hay cuenta configurada o está inactiva
        """
        pass
    
    # =========================================
    # MÉTODOS COMUNES (heredados por todos)
    # =========================================
    
    def start(self):
        """
        Inicia la transmisión a la plataforma.
        
        Proceso:
        1. Valida credenciales
        2. Obtiene URL de destino
        3. Construye comando FFmpeg
        4. Ejecuta proceso
        
        Returns:
            subprocess.Popen: Proceso FFmpeg en ejecución
        
        Raises:
            ValueError: Si hay errores de configuración
            Exception: Si falla al iniciar FFmpeg
        """
        logger.info(f"🚀 Iniciando transmisión a {self.PLATFORM_NAME}")
        
        # 1. Validar credenciales
        self.validate_account_credentials()
        
        # 2. Obtener URL destino
        destination_url = self.get_rtmp_destination_url()
        
        # 3. Construir comando FFmpeg
        command = self.build_ffmpeg_command(destination_url)
        
        # 4. Log del comando completo
        logger.info(f"🔧 Comando FFmpeg COMPLETO:")
        logger.info(f"   {' '.join(command)}")
        
        # 5. Iniciar proceso SIN archivos de log (stdout/stderr en tiempo real)
        import os
        
        self.process = subprocess.Popen(
            command,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            universal_newlines=True,
            creationflags=subprocess.CREATE_NEW_PROCESS_GROUP if os.name == "nt" else 0
        )
        
        logger.info(f"✅ Proceso FFmpeg iniciado (PID: {self.process.pid})")
        
        # 6. Verificar si el proceso murió inmediatamente
        import time
        time.sleep(0.5)  # Esperar medio segundo
        
        if self.process.poll() is not None:
            # El proceso terminó inmediatamente - hay un error
            stdout, stderr = self.process.communicate()
            error_msg = stderr if stderr else stdout
            logger.error(f"❌ FFmpeg falló inmediatamente:")
            logger.error(f"   {error_msg}")
            raise Exception(f"FFmpeg falló al iniciar: {error_msg[:500]}")
        
        logger.info(f"✅ FFmpeg corriendo correctamente")
        
        return self.process
    
    def stop(self):
        """
        Detiene la transmisión de forma ordenada.
        
        Intenta terminar el proceso con SIGTERM primero,
        y si no responde en 5 segundos, lo fuerza con SIGKILL.
        """
        if not self.process:
            logger.warning(f"⚠️ No hay proceso activo para {self.PLATFORM_NAME}")
            return
        
        if self.process.poll() is not None:
            logger.info(f"ℹ️ Proceso ya estaba detenido (PID: {self.process.pid})")
            return
        
        logger.info(f"🛑 Deteniendo transmisión a {self.PLATFORM_NAME} (PID: {self.process.pid})")
        
        try:
            self.process.terminate()  # SIGTERM (cierre ordenado)
            self.process.wait(timeout=5)
            logger.info(f"✅ Proceso detenido correctamente")
        except subprocess.TimeoutExpired:
            logger.warning(f"⚠️ Proceso no respondió, forzando cierre...")
            self.process.kill()  # SIGKILL (cierre forzado)
            self.process.wait()
            logger.info(f"✅ Proceso forzado a detenerse")
    
    def is_running(self):
        """
        Verifica si el proceso FFmpeg está en ejecución.
        
        Returns:
            bool: True si está corriendo, False si no
        """
        if not self.process:
            return False
        
        return self.process.poll() is None
    
    def get_pid(self):
        """
        Obtiene el PID del proceso FFmpeg.
        
        Returns:
            int or None: PID del proceso, o None si no está iniciado
        """
        return self.process.pid if self.process else None