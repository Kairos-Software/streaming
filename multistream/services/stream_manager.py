"""
STREAM MANAGER
Orquestador central de retransmisiones multi-plataforma.

Este módulo se encarga de:
- Decidir qué streamer usar según la plataforma solicitada
- Mantener registro de procesos FFmpeg activos
- Coordinar inicio/detención de transmisiones
- Gestionar estados en base de datos
"""

import logging
from datetime import datetime
from django.conf import settings
from multistream.models import EstadoRetransmision
from core.models import CanalTransmision
from .youtube_streamer import YouTubeStreamer

logger = logging.getLogger(__name__)

# Registro en memoria de procesos activos
# Estructura: {user_id: {platform: proceso_ffmpeg}}
ACTIVE_PROCESSES = {}


class StreamManager:
    """
    Gestor central de retransmisiones.
    
    Maneja múltiples plataformas de forma unificada y mantiene
    sincronizado el estado en memoria y en base de datos.
    """
    
    # Registro de streamers disponibles
    AVAILABLE_STREAMERS = {
        'youtube': YouTubeStreamer,
        # Futuro: 'facebook': FacebookStreamer,
        # Futuro: 'twitch': TwitchStreamer,
    }
    
    @classmethod
    def start_stream(cls, user, platform, force=False):
        """
        Inicia una transmisión en la plataforma especificada.
        
        Proceso:
        1. Valida que la plataforma esté soportada
        2. Obtiene la URL HLS del canal del usuario
        3. Verifica que no haya transmisión activa (o fuerza si force=True)
        4. Crea el streamer correspondiente
        5. Inicia el proceso FFmpeg
        6. Registra el estado en BD y memoria
        
        Args:
            user: Usuario Django
            platform (str): Plataforma destino ('youtube', 'facebook', etc)
            force (bool): Si True, detiene transmisión activa antes de iniciar
        
        Returns:
            dict: Resultado de la operación
                {
                    'success': bool,
                    'pid': int (si success=True),
                    'message': str (si success=False),
                    'requires_confirmation': bool (si hay stream activo)
                }
        """
        try:
            # 1. Validar plataforma
            if platform not in cls.AVAILABLE_STREAMERS:
                available = ', '.join(cls.AVAILABLE_STREAMERS.keys())
                return {
                    'success': False,
                    'message': f"Plataforma '{platform}' no soportada. Disponibles: {available}"
                }
            
            # 2. Obtener URL HLS del canal
            source_url = cls._get_channel_hls_url(user)
            if not source_url:
                return {
                    'success': False,
                    'message': "No hay transmisión activa en tu canal"
                }
            
            # 3. Verificar que no esté ya retransmitiendo
            existing_stream = EstadoRetransmision.objects.filter(
                usuario=user,
                plataforma=platform,
                detenido_en__isnull=True
            ).first()
            
            if existing_stream:
                if not force:
                    # Retornar aviso para que frontend pida confirmación
                    logger.warning(f"⚠️ {platform} ya está activo para {user.username} - requiere confirmación")
                    return {
                        'success': False,
                        'requires_confirmation': True,
                        'message': f'Ya hay una transmisión activa en {platform.title()}. ¿Deseas detenerla e iniciar una nueva?'
                    }
                else:
                    # Usuario confirmó, detener transmisión anterior
                    logger.info(f"🔄 Forzando nueva transmisión en {platform} - deteniendo anterior")
                    cls.stop_stream(user, platform)
            
            # 4. Crear streamer
            streamer_class = cls.AVAILABLE_STREAMERS[platform]
            streamer = streamer_class(user, source_url)
            
            logger.info(f"🎬 Iniciando {platform} para {user.username}")
            
            # 5. Iniciar proceso FFmpeg
            process = streamer.start()
            
            # 6. Registrar en memoria
            if user.id not in ACTIVE_PROCESSES:
                ACTIVE_PROCESSES[user.id] = {}
            
            ACTIVE_PROCESSES[user.id][platform] = {
                'process': process,
                'streamer': streamer
            }
            
            # 7. Registrar en BD
            EstadoRetransmision.objects.create(
                usuario=user,
                plataforma=platform,
                proceso_id=process.pid,
                estado='activo'
            )
            
            logger.info(f"✅ {platform.title()} iniciado correctamente (PID: {process.pid})")
            
            return {
                'success': True,
                'pid': process.pid
            }
            
        except ValueError as e:
            # Errores de validación (credenciales, configuración, etc)
            logger.warning(f"⚠️ Error de validación en {platform}: {e}")
            
            # Registrar fallo en BD
            EstadoRetransmision.objects.create(
                usuario=user,
                plataforma=platform,
                estado='error',
                mensaje_error=str(e),
                detenido_en=datetime.now()
            )
            
            return {
                'success': False,
                'message': str(e)
            }
            
        except Exception as e:
            # Errores inesperados
            logger.exception(f"❌ Error inesperado iniciando {platform}")
            
            # Registrar fallo en BD
            EstadoRetransmision.objects.create(
                usuario=user,
                plataforma=platform,
                estado='error',
                mensaje_error=f"Error interno: {str(e)}",
                detenido_en=datetime.now()
            )
            
            return {
                'success': False,
                'message': f"Error interno al iniciar {platform}"
            }
    
    @classmethod
    def stop_stream(cls, user, platform):
        """
        Detiene una transmisión activa.
        
        Args:
            user: Usuario Django
            platform (str): Plataforma a detener
        
        Returns:
            dict: Resultado de la operación
                {
                    'success': bool,
                    'message': str (opcional)
                }
        """
        try:
            # 1. Buscar proceso en memoria
            process_data = ACTIVE_PROCESSES.get(user.id, {}).get(platform)
            
            if process_data:
                streamer = process_data['streamer']
                streamer.stop()
                
                # Limpiar de memoria
                ACTIVE_PROCESSES[user.id].pop(platform, None)
                
                # Si no quedan procesos para este usuario, limpiar entrada
                if not ACTIVE_PROCESSES[user.id]:
                    del ACTIVE_PROCESSES[user.id]
            
            # 2. Actualizar estado en BD
            estado = EstadoRetransmision.objects.filter(
                usuario=user,
                plataforma=platform,
                detenido_en__isnull=True
            ).first()
            
            if estado:
                estado.estado = 'detenido'
                estado.detenido_en = datetime.now()
                estado.save()
            
            logger.info(f"🛑 {platform.title()} detenido para {user.username}")
            
            return {'success': True}
            
        except Exception as e:
            logger.exception(f"❌ Error deteniendo {platform}")
            return {
                'success': False,
                'message': str(e)
            }
    
    @classmethod
    def get_active_streams(cls, user):
        """
        Obtiene las retransmisiones activas del usuario.
        
        Args:
            user: Usuario Django
        
        Returns:
            list: Lista de plataformas activas
                [
                    {
                        'plataforma': 'youtube',
                        'pid': 12345,
                        'activo': True
                    },
                    ...
                ]
        """
        active = []
        
        user_processes = ACTIVE_PROCESSES.get(user.id, {})
        
        for platform, data in user_processes.items():
            streamer = data['streamer']
            active.append({
                'plataforma': platform,
                'pid': streamer.get_pid(),
                'activo': streamer.is_running()
            })
        
        return active
    
    @classmethod
    def cleanup_dead_processes(cls):
        """
        Limpia procesos FFmpeg que hayan terminado inesperadamente.
        
        Esto es útil para ejecutar periódicamente y mantener
        sincronizado el estado real con el estado en memoria/BD.
        """
        cleaned = 0
        
        for user_id in list(ACTIVE_PROCESSES.keys()):
            for platform in list(ACTIVE_PROCESSES[user_id].keys()):
                streamer = ACTIVE_PROCESSES[user_id][platform]['streamer']
                
                if not streamer.is_running():
                    logger.warning(f"⚠️ Proceso huérfano detectado: User {user_id} - {platform}")
                    
                    # Limpiar de memoria
                    ACTIVE_PROCESSES[user_id].pop(platform)
                    cleaned += 1
                    
                    # Actualizar BD
                    EstadoRetransmision.objects.filter(
                        usuario_id=user_id,
                        plataforma=platform,
                        detenido_en__isnull=True
                    ).update(
                        estado='error',
                        mensaje_error='Proceso terminado inesperadamente',
                        detenido_en=datetime.now()
                    )
            
            # Limpiar entrada de usuario si no tiene procesos
            if not ACTIVE_PROCESSES[user_id]:
                del ACTIVE_PROCESSES[user_id]
        
        if cleaned > 0:
            logger.info(f"🧹 Limpiados {cleaned} procesos huérfanos")
        
        return cleaned
    
    @staticmethod
    def _get_channel_hls_url(user):
        """
        Obtiene la URL HLS del programa final del usuario.
        
        El programa final está en: hls/program/{username}.m3u8
        
        Args:
            user: Usuario Django
        
        Returns:
            str or None: URL HLS del programa si está en vivo, None si no
        """
        try:
            canal = CanalTransmision.objects.get(usuario=user)
            
            if not canal.en_vivo:
                logger.warning(f"⚠️ Canal de {user.username} no está en vivo")
                return None
            
            # Usar URL del modelo si existe
            if canal.url_hls:
                logger.info(f"📡 URL HLS del canal (BD): {canal.url_hls}")
                return canal.url_hls
            
            # Construir URL del programa final
            # Formato: http://IP:8080/hls/program/{username}.m3u8
            hls_base = settings.HLS_SERVER_URL_HTTP
            url_programa = f"{hls_base}/program/{user.username}.m3u8"
            
            logger.info(f"📡 URL HLS programa: {url_programa}")
            return url_programa
            
        except CanalTransmision.DoesNotExist:
            logger.error(f"❌ No existe canal para {user.username}")
            return None