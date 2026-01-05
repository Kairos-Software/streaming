# core/routing.py
from django.urls import re_path
from core.consumers import PanelConsumer

websocket_urlpatterns = [
    re_path(r'ws/panel/$', PanelConsumer.as_asgi()),
]
