"""
STREAM MANAGER - ORIGINAL
Sin auto-restart. Facebook streamer maneja los timestamps con N/FR/TB.
"""

import logging
from datetime import datetime
from django.conf import settings
from multistream.models import EstadoRetransmision
from core.models import CanalTransmision
from .youtube_streamer import YouTubeStreamer
from .facebook_streamer import FacebookStreamer

logger = logging.getLogger(__name__)

ACTIVE_PROCESSES = {}


class StreamManager:

    AVAILABLE_STREAMERS = {
        'youtube': YouTubeStreamer,
        'facebook': FacebookStreamer,
    }

    @classmethod
    def start_stream(cls, user, platform, force=False):
        try:
            if platform not in cls.AVAILABLE_STREAMERS:
                available = ', '.join(cls.AVAILABLE_STREAMERS.keys())
                return {
                    'success': False,
                    'message': f"Plataforma '{platform}' no soportada. Disponibles: {available}"
                }

            source_url = cls._get_channel_hls_url(user)
            if not source_url:
                return {
                    'success': False,
                    'message': "No hay transmisión activa en tu canal"
                }

            existing_stream = EstadoRetransmision.objects.filter(
                usuario=user,
                plataforma=platform,
                detenido_en__isnull=True
            ).first()

            if existing_stream:
                if not force:
                    logger.warning(f"⚠️ {platform} ya está activo para {user.username}")
                    return {
                        'success': False,
                        'requires_confirmation': True,
                        'message': f'Ya hay una transmisión activa en {platform.title()}. ¿Deseas detenerla e iniciar una nueva?'
                    }
                else:
                    logger.info(f"🔄 Forzando nueva transmisión en {platform}")
                    cls.stop_stream(user, platform)

            streamer_class = cls.AVAILABLE_STREAMERS[platform]
            streamer = streamer_class(user, source_url)

            logger.info(f"🎬 Iniciando {platform} para {user.username}")

            process = streamer.start()

            if user.id not in ACTIVE_PROCESSES:
                ACTIVE_PROCESSES[user.id] = {}

            ACTIVE_PROCESSES[user.id][platform] = {
                'process': process,
                'streamer': streamer
            }

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
            logger.warning(f"⚠️ Error de validación en {platform}: {e}")
            EstadoRetransmision.objects.create(
                usuario=user,
                plataforma=platform,
                estado='error',
                mensaje_error=str(e),
                detenido_en=datetime.now()
            )
            return {'success': False, 'message': str(e)}

        except Exception as e:
            logger.exception(f"❌ Error inesperado iniciando {platform}")
            EstadoRetransmision.objects.create(
                usuario=user,
                plataforma=platform,
                estado='error',
                mensaje_error=f"Error interno: {str(e)}",
                detenido_en=datetime.now()
            )
            return {'success': False, 'message': f"Error interno al iniciar {platform}"}

    @classmethod
    def stop_stream(cls, user, platform):
        try:
            process_data = ACTIVE_PROCESSES.get(user.id, {}).get(platform)

            if process_data:
                streamer = process_data['streamer']
                streamer.stop()
                ACTIVE_PROCESSES[user.id].pop(platform, None)
                if not ACTIVE_PROCESSES[user.id]:
                    del ACTIVE_PROCESSES[user.id]

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
            return {'success': False, 'message': str(e)}

    @classmethod
    def get_active_streams(cls, user):
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
        cleaned = 0
        for user_id in list(ACTIVE_PROCESSES.keys()):
            for platform in list(ACTIVE_PROCESSES[user_id].keys()):
                streamer = ACTIVE_PROCESSES[user_id][platform]['streamer']
                if not streamer.is_running():
                    logger.warning(f"⚠️ Proceso huérfano: User {user_id} - {platform}")
                    ACTIVE_PROCESSES[user_id].pop(platform)
                    cleaned += 1
                    EstadoRetransmision.objects.filter(
                        usuario_id=user_id,
                        plataforma=platform,
                        detenido_en__isnull=True
                    ).update(
                        estado='error',
                        mensaje_error='Proceso terminado inesperadamente',
                        detenido_en=datetime.now()
                    )
            if not ACTIVE_PROCESSES[user_id]:
                del ACTIVE_PROCESSES[user_id]
        if cleaned > 0:
            logger.info(f"🧹 Limpiados {cleaned} procesos huérfanos")
        return cleaned

    @staticmethod
    def _get_channel_hls_url(user):
        try:
            canal = CanalTransmision.objects.get(usuario=user)
            if not canal.en_vivo:
                logger.warning(f"⚠️ Canal de {user.username} no está en vivo")
                return None
            if canal.url_hls:
                logger.info(f"📡 URL HLS del canal (BD): {canal.url_hls}")
                return canal.url_hls
            hls_base = settings.HLS_SERVER_URL_HTTP
            url_programa = f"{hls_base}/program/{user.username}.m3u8"
            logger.info(f"📡 URL HLS programa: {url_programa}")
            return url_programa
        except CanalTransmision.DoesNotExist:
            logger.error(f"❌ No existe canal para {user.username}")
            return None
