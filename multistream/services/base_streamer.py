"""
BASE STREAMER - Clase abstracta base para todas las plataformas

ARREGLO CRÍTICO:
- Los logs de FFmpeg van a archivo (/tmp/ffmpeg_*.log)
- NO usa PIPE que se puede llenar y bloquear FFmpeg
"""

from abc import ABC, abstractmethod
import subprocess
import logging
import os

logger = logging.getLogger(__name__)


class BaseStreamer(ABC):
    """
    Clase base abstracta para gestionar transmisiones a plataformas externas.
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
        self.log_file = None  # Archivo de log
    
    # =========================================
    # MÉTODOS ABSTRACTOS (obligatorios)
    # =========================================
    
    @abstractmethod
    def get_rtmp_destination_url(self):
        """
        Construye la URL RTMP de destino de la plataforma.
        
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
        
        Args:
            destination_url (str): URL RTMP de destino
        
        Returns:
            list: Lista con el comando FFmpeg
        """
        pass
    
    @abstractmethod
    def validate_account_credentials(self):
        """
        Valida que el usuario tenga credenciales configuradas.
        
        Raises:
            ValueError: Si no hay cuenta configurada o está inactiva
        """
        pass
    
    # =========================================
    # MÉTODOS COMUNES
    # =========================================
    
    def start(self):
        """
        Inicia la transmisión a la plataforma.
        
        ARREGLO CRÍTICO:
        - Usa archivo de log en lugar de PIPE
        - Evita que FFmpeg se bloquee cuando el pipe se llena
        
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
        
        # 5. Crear archivo de log
        # CRÍTICO: Escribir a archivo en lugar de PIPE
        log_dir = '/tmp/ffmpeg_logs'
        os.makedirs(log_dir, exist_ok=True)
        
        log_filename = f"ffmpeg_{self.PLATFORM_NAME}_{self.user.username}.log"
        log_path = os.path.join(log_dir, log_filename)
        
        self.log_file = open(log_path, 'w')
        
        logger.info(f"📝 Logs FFmpeg: {log_path}")
        
        # 6. Iniciar proceso CON ARCHIVO DE LOG
        self.process = subprocess.Popen(
            command,
            stdin=subprocess.DEVNULL,
            stdout=self.log_file,  # ✅ Archivo en lugar de PIPE
            stderr=subprocess.STDOUT,  # Combinar stderr con stdout
            universal_newlines=True,
            creationflags=subprocess.CREATE_NEW_PROCESS_GROUP if os.name == "nt" else 0
        )
        
        logger.info(f"✅ Proceso FFmpeg iniciado (PID: {self.process.pid})")
        
        # 7. Verificar si el proceso murió inmediatamente
        import time
        time.sleep(1)  # Esperar 1 segundo
        
        if self.process.poll() is not None:
            # El proceso terminó - leer error del archivo
            self.log_file.close()
            
            with open(log_path, 'r') as f:
                error_msg = f.read()
            
            logger.error(f"❌ FFmpeg falló inmediatamente:")
            logger.error(f"   {error_msg[-1000:]}")  # Últimas 1000 chars
            
            raise Exception(f"FFmpeg falló al iniciar. Ver: {log_path}")
        
        logger.info(f"✅ FFmpeg corriendo correctamente")
        
        return self.process
    
    def stop(self):
        """
        Detiene la transmisión de forma ordenada.
        """
        if not self.process:
            logger.warning(f"⚠️ No hay proceso activo para {self.PLATFORM_NAME}")
            return
        
        if self.process.poll() is not None:
            logger.info(f"ℹ️ Proceso ya estaba detenido (PID: {self.process.pid})")
            # Cerrar archivo de log si está abierto
            if self.log_file and not self.log_file.closed:
                self.log_file.close()
            return
        
        logger.info(f"🛑 Deteniendo transmisión a {self.PLATFORM_NAME} (PID: {self.process.pid})")
        
        try:
            self.process.terminate()  # SIGTERM
            self.process.wait(timeout=5)
            logger.info(f"✅ Proceso detenido correctamente")
        except subprocess.TimeoutExpired:
            logger.warning(f"⚠️ Proceso no respondió, forzando cierre...")
            self.process.kill()  # SIGKILL
            self.process.wait()
            logger.info(f"✅ Proceso forzado a detenerse")
        finally:
            # Cerrar archivo de log
            if self.log_file and not self.log_file.closed:
                self.log_file.close()
    
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