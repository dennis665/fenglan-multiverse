#! 定義遊戲專屬的 WebSocket 路由
from django.urls import re_path

from . import consumers

websocket_urlpatterns = [
    #! Godot 連線使用的路徑
    re_path(r"ws/game/world/$", consumers.GameConsumer.as_asgi()),  # type: ignore
]  # * 對應 Godot 中的 ws://127.0.0.1:8000/ws/game/world/
