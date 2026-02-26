"""
BASE STREAMER - Clase abstracta base para todas las plataformas

CRÍTICO: FFmpeg escribe a archivo de log, NO a PIPE.
Con PIPE, si nadie lee el pipe se llena y FFmpeg se bloquea/muere.
Con archivo, FFmpeg puede escribir indefinidamente sin bloquearse.
"""

from abc import ABC, abstractmethod
import subprocess
import logging
import os

logger = logging.getLogger(__name__)


class BaseStreamer(ABC):

    PLATFORM_NAME = None

    def __init__(self, user, source_url):
        self.user = user
        self.source_url = source_url
        self.process = None
        self._log_file = None

    @abstractmethod
    def get_rtmp_destination_url(self):
        pass

    @abstractmethod
    def build_ffmpeg_command(self, destination_url):
        pass

    @abstractmethod
    def validate_account_credentials(self):
        pass

    def start(self):
        logger.info(f"🚀 Iniciando transmisión a {self.PLATFORM_NAME}")

        self.validate_account_credentials()
        destination_url = self.get_rtmp_destination_url()
        command = self.build_ffmpeg_command(destination_url)

        logger.info(f"🔧 Comando FFmpeg COMPLETO:")
        logger.info(f"   {' '.join(command)}")

        # Escribir logs a archivo para que FFmpeg nunca se bloquee
        log_dir = '/tmp/ffmpeg_logs'
        os.makedirs(log_dir, exist_ok=True)
        log_path = f"{log_dir}/ffmpeg_{self.PLATFORM_NAME}_{self.user.username}.log"

        # Abrir en modo binario - FFmpeg escribe bytes, no texto
        self._log_file = open(log_path, 'wb')

        logger.info(f"📝 Log FFmpeg: {log_path}")

        self.process = subprocess.Popen(
            command,
            stdin=subprocess.DEVNULL,
            stdout=self._log_file,
            stderr=subprocess.STDOUT,
            creationflags=subprocess.CREATE_NEW_PROCESS_GROUP if os.name == "nt" else 0
        )

        logger.info(f"✅ Proceso FFmpeg iniciado (PID: {self.process.pid})")

        import time
        time.sleep(1)

        if self.process.poll() is not None:
            self._log_file.flush()
            self._log_file.close()
            try:
                with open(log_path, 'rb') as f:
                    error_msg = f.read().decode('utf-8', errors='replace')
            except Exception:
                error_msg = "no se pudo leer el log"
            logger.error(f"❌ FFmpeg falló inmediatamente: {error_msg[-500:]}")
            raise Exception(f"FFmpeg falló al iniciar. Ver: {log_path}")

        logger.info(f"✅ FFmpeg corriendo correctamente")
        return self.process

    def stop(self):
        if not self.process:
            logger.warning(f"⚠️ No hay proceso activo para {self.PLATFORM_NAME}")
            return

        if self.process.poll() is not None:
            logger.info(f"ℹ️ Proceso ya estaba detenido (PID: {self.process.pid})")
            self._close_log()
            return

        logger.info(f"🛑 Deteniendo {self.PLATFORM_NAME} (PID: {self.process.pid})")

        try:
            self.process.terminate()
            self.process.wait(timeout=5)
            logger.info(f"✅ Proceso detenido correctamente")
        except subprocess.TimeoutExpired:
            self.process.kill()
            self.process.wait()
            logger.info(f"✅ Proceso forzado a detenerse")
        finally:
            self._close_log()

    def _close_log(self):
        if self._log_file and not self._log_file.closed:
            self._log_file.close()

    def is_running(self):
        if not self.process:
            return False
        return self.process.poll() is None

    def get_pid(self):
        return self.process.pid if self.process else None