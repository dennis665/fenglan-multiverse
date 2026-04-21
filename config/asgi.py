#! 專案 ASGI 進入點，整合 HTTP 與 WebSocket
import os

from channels.auth import AuthMiddlewareStack
from channels.routing import ProtocolTypeRouter, URLRouter
from django.core.asgi import get_asgi_application

from .routing import websocket_urlpatterns as game_ws_urls

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

application = ProtocolTypeRouter(
    {
        "http": get_asgi_application(),  #! 處理標準網頁請求
        "websocket": AuthMiddlewareStack(
            URLRouter(
                game_ws_urls  #! 處理遊戲連線請求
            )
        ),
    }
)