import json

from channels.generic.websocket import AsyncWebsocketConsumer
from django.utils.translation import gettext as _


class GameConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        #! 玩家嘗試連線進入世界
        await self.accept()
        # * 這裡未來可以加入群組（Group），讓村莊裡的所有人都能看到彼此

    async def disconnect(self, close_code):
        #! 玩家離開世界
        pass

    async def receive(self, text_data):
        #! 接收來自 Godot 的封包 (例如座標或對話)
        data = json.loads(text_data)
        message = data.get("message", "")

        #! 回傳格式化後的訊息給 Godot
        response_text = f"{_('伺服器已收到')}: {message}"

        await self.send(
            text_data=json.dumps(
                {"message": response_text, "status": "success"}, ensure_ascii=False
            )
        )  # * 確保傳回 JSON 格式
