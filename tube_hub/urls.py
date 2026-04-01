from django.urls import path

from . import views

app_name = "tube_hub"

urlpatterns = [
    #! 1. 搜尋與首頁 (網址: /tube_hub/)
    path("", views.search_youtube, name="search"),
    #! 2. 下載處理 API (網址: /tube_hub/download/)
    path("download/", views.download_resource, name="download"),
    #! 3. 影音播放與學習面板 (網址: /tube_hub/player/<id>/)
    path("player/<int:resource_id>/", views.player_room, name="player"),
]
