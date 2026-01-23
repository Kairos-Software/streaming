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
            
            # Fallback: construir la URL manualmente
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
            # Validar que existe configuración
            if platform == 'youtube':
                cuenta = CuentaYouTube.objects.filter(
                    usuario=self.usuario,
                    activo=True
                ).first()
                
                if not cuenta:
                    return {
                        'success': False,
                        'message': 'No hay cuenta de YouTube configurada'
                    }
                
                if not cuenta.clave_transmision or not cuenta.url_ingestion:
                    return {
                        'success': False,
                        'message': 'La configuración de YouTube está incompleta'
                    }
                
                # Construir URL RTMP completa
                url_base = cuenta.url_ingestion.rstrip('/')
                url_destino = f"{url_base}/{cuenta.clave_transmision}"
            
            else:
                return {
                    'success': False,
                    'message': f'Plataforma {platform} no implementada aún'
                }
            
            # Obtener URL HLS origen
            url_hls = self.obtener_url_hls()
            if not url_hls:
                return {
                    'success': False,
                    'message': 'No hay transmisión activa para retransmitir'
                }
            
            # Verificar si ya existe retransmisión activa
            estado_existente = EstadoRetransmision.objects.filter(
                usuario=self.usuario,
                plataforma=platform,
                detenido_en__isnull=True
            ).first()
            
            if estado_existente:
                return {
                    'success': False,
                    'message': f'Ya existe una retransmisión activa en {platform}'
                }
            
            # Iniciar FFmpeg
            proceso = self._iniciar_ffmpeg(url_hls, url_destino)
            
            # Guardar proceso en memoria
            if self.usuario.id not in RESTREAM_PROCESSES:
                RESTREAM_PROCESSES[self.usuario.id] = {}
            RESTREAM_PROCESSES[self.usuario.id][platform] = proceso
            
            # Crear registro en base de datos
            EstadoRetransmision.objects.create(
                usuario=self.usuario,
                plataforma=platform,
                proceso_id=proceso.pid,
                estado='activo'
            )
            
            logger.info(f"✅ Retransmisión iniciada: {platform} (PID: {proceso.pid})")
            
            return {
                'success': True,
                'message': f'Retransmisión en {platform} iniciada correctamente',
                'pid': proceso.pid
            }
            
        except Exception as e:
            logger.error(f"❌ Error iniciando {platform}: {str(e)}")
            
            # Registrar error
            EstadoRetransmision.objects.create(
                usuario=self.usuario,
                plataforma=platform,
                estado='error',
                mensaje_error=str(e),
                detenido_en=datetime.now()
            )
            
            return {
                'success': False,
                'message': f'Error: {str(e)}'
            }
    
    def detener_plataforma(self, platform):
        """
        Detiene retransmisión en una plataforma específica
        """
        try:
            # Buscar proceso en memoria
            proceso = None
            if self.usuario.id in RESTREAM_PROCESSES:
                proceso = RESTREAM_PROCESSES[self.usuario.id].get(platform)
            
            # Buscar estado en BD
            estado = EstadoRetransmision.objects.filter(
                usuario=self.usuario,
                plataforma=platform,
                detenido_en__isnull=True
            ).first()
            
            if not estado and not proceso:
                return {
                    'success': False,
                    'message': f'No hay retransmisión activa en {platform}'
                }
            
            # Detener proceso FFmpeg
            if proceso and proceso.poll() is None:  # Si está corriendo
                try:
                    proceso.terminate()
                    proceso.wait(timeout=5)
                    logger.info(f"✅ Proceso FFmpeg detenido correctamente")
                except subprocess.TimeoutExpired:
                    proceso.kill()
                    logger.warning(f"⚠️ Proceso FFmpeg forzado a detenerse")
                except Exception as e:
                    logger.error(f"❌ Error deteniendo proceso: {str(e)}")
            
            # Limpiar de memoria
            if self.usuario.id in RESTREAM_PROCESSES:
                RESTREAM_PROCESSES[self.usuario.id].pop(platform, None)
                if not RESTREAM_PROCESSES[self.usuario.id]:
                    del RESTREAM_PROCESSES[self.usuario.id]
            
            # Actualizar estado en BD
            if estado:
                estado.estado = 'detenido'
                estado.detenido_en = datetime.now()
                estado.save()
            
            logger.info(f"✅ Retransmisión detenida: {platform}")
            
            return {
                'success': True,
                'message': f'Retransmisión en {platform} detenida correctamente'
            }
            
        except Exception as e:
            logger.error(f"❌ Error deteniendo {platform}: {str(e)}")
            return {
                'success': False,
                'message': f'Error: {str(e)}'
            }
    
    def _iniciar_ffmpeg(self, url_hls, url_rtmp_destino):
        """
        Inicia proceso FFmpeg para reenviar HLS → RTMP
        """
        
        ffmpeg_bin = settings.FFMPEG_BIN_PATH
        
        comando = [
            ffmpeg_bin,
            
            # Input: Tu HLS existente
            '-re',                               # Leer en tiempo real
            '-i', url_hls,
            
            # Copiar sin recodificar (más eficiente)
            '-c:v', 'copy',                      # Video sin tocar
            '-c:a', 'copy',                      # Audio sin tocar
            
            # Output: RTMP
            '-f', 'flv',                         # Formato para RTMP
            '-flvflags', 'no_duration_filesize',
            
            # Manejo de errores
            '-reconnect', '1',
            '-reconnect_streamed', '1',
            '-reconnect_delay_max', '10',
            
            url_rtmp_destino
        ]
        
        logger.info(f"🚀 Comando FFmpeg: {' '.join(comando)}")
        
        # Ejecutar en background
        proceso = subprocess.Popen(
            comando,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            stdin=subprocess.PIPE,
            creationflags=subprocess.CREATE_NEW_PROCESS_GROUP if os.name == "nt" else 0
        )
        
        return proceso
    
    def detener_todas(self):
        """
        Detiene todas las retransmisiones activas del usuario
        """
        estados_activos = EstadoRetransmision.objects.filter(
            usuario=self.usuario,
            detenido_en__isnull=True
        )
        
        resultados = []
        for estado in estados_activos:
            resultado = self.detener_plataforma(estado.plataforma)
            resultados.append({
                'platform': estado.plataforma,
                **resultado
            })
        
        return resultados
    
    @staticmethod
    def limpiar_procesos_huerfanos():
        """
        Limpia procesos que ya no están corriendo
        """
        for user_id in list(RESTREAM_PROCESSES.keys()):
            for platform in list(RESTREAM_PROCESSES[user_id].keys()):
                proceso = RESTREAM_PROCESSES[user_id][platform]
                if proceso.poll() is not None:  # Si ya terminó
                    logger.warning(f"⚠️ Proceso huérfano detectado: user {user_id}, {platform}")
                    RESTREAM_PROCESSES[user_id].pop(platform)
            
            if not RESTREAM_PROCESSES[user_id]:
                del RESTREAM_PROCESSES[user_id]