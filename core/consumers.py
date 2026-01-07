import logging
from channels.generic.websocket import AsyncJsonWebsocketConsumer

logger = logging.getLogger(__name__)


class PanelConsumer(AsyncJsonWebsocketConsumer):

    async def connect(self):
        user = self.scope.get("user")
        if user and user.is_authenticated:
            self.group_name = f"usuario_{user.id}"
            await self.channel_layer.group_add(self.group_name, self.channel_name)
            await self.accept()
            logger.info(f"[WS] Usuario {user.username} ({user.id}) conectado")
        else:
            logger.warning("[WS] Usuario no autenticado, conexión rechazada")
            await self.close(code=4001)

    async def disconnect(self, close_code):
        if hasattr(self, "group_name"):
            await self.channel_layer.group_discard(self.group_name, self.channel_name)
            logger.info(f"[WS] Usuario desconectado ({close_code})")

    # ======================
    # HANDLERS DESDE CHANNELS
    # ======================

    async def estado_camaras(self, event):
        await self.send_json({
            "tipo": "estado_camaras",
            "cameras": event.get("cameras", {})
        })

    async def camara_actualizada(self, event):
        await self.send_json({
            "tipo": "camara_actualizada",
            "cam_index": event.get("cam_index"),
            "estado": event.get("estado"),
            "authorized": event.get("authorized"),
            "hls_url": event.get("hls_url"),  # consistente con el front
        })

    async def camara_eliminada(self, event):
        await self.send_json({
            "tipo": "camara_eliminada",
            "cam_index": event.get("cam_index")
        })

    async def estado_canal(self, event):
        await self.send_json({
            "tipo": "estado_canal",
            "en_vivo": event.get("en_vivo", False),
            "hls_url": event.get("hls_url"),  # corregido: antes era url_hls
        })
