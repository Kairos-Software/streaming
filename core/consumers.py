from channels.generic.websocket import AsyncJsonWebsocketConsumer


class PanelConsumer(AsyncJsonWebsocketConsumer):
    async def connect(self):
        user = self.scope["user"]
        if user.is_authenticated:
            self.group_name = f"usuario_{user.id}"
            await self.channel_layer.group_add(self.group_name, self.channel_name)
            await self.accept()
            print(f"✅ [WS] Usuario {user.id} conectado al grupo {self.group_name}")
        else:
            await self.close()

    async def disconnect(self, close_code):
        if hasattr(self, 'group_name'):
            await self.channel_layer.group_discard(self.group_name, self.channel_name)
            print(f"⚠️ [WS] Usuario desconectado del grupo {self.group_name}")

    # ======================
    # HANDLERS
    # ======================
    async def estado_camaras(self, event):
        """Envía el estado completo de todas las cámaras (snapshot inicial)"""
        await self.send_json({
            "tipo": "estado_camaras", 
            "cameras": event.get("cameras", {})
        })

    async def camara_actualizada(self, event):
        """Envía la actualización de UNA cámara específica"""
        await self.send_json({
            "tipo": "camara_actualizada",
            "cam_index": event.get("cam_index"),
            "estado": event.get("estado"),
            "authorized": event.get("authorized"),
            "hls_url": event.get("hls_url"),
        })

    async def camara_eliminada(self, event):
        """Notifica que una cámara fue eliminada"""
        await self.send_json({
            "tipo": "camara_eliminada", 
            "cam_index": event.get("cam_index")
        })

    async def estado_canal(self, event):
        """Notifica el estado del canal de transmisión (preview principal)"""
        await self.send_json({
            "tipo": "estado_canal",
            "en_vivo": event.get("en_vivo", False),
            "hls_url": event.get("hls_url")  # ← CRÍTICO: debe incluir hls_url
        })