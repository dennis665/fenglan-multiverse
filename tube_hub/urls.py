from django.urls import path

from . import views

app_name = "tube_hub"

urlpatterns = [
    #! 搜尋與首頁
    path("", views.search_youtube, name="search"),
    #! 下載處理介面
    path("download/", views.download_resource, name="download"),
    #! 影音播放與學習面板
    path("player/<int:resource_id>/", views.player_room, name="player"),
    path("collect_public_resource/", views.collect_public_resource, name="collect_public_resource"),
    path("toggle_public/", views.toggle_public_status, name="toggle_public_status"),
    path("move_resource/", views.move_resource, name="move_resource"),
    path("update_notes/", views.update_notes, name="update_notes"),
    path("delete_resource/", views.delete_resource, name="delete_resource"),
]
