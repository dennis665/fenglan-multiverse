#! 遊戲中心路由
from django.urls import path

from . import views

app_name = "games"

urlpatterns = [
    # * 倖存者生存遊戲
    path("survivor/", views.survivor_index, name="survivor_index"),
    path("api/survivor/save/", views.survivor_save_api, name="survivor_save_api"),
    path("api/survivor/upgrade/", views.buy_upgrade_api, name="buy_upgrade_api"),
    # * 未來可在此新增路徑
    # path('tetris/', views.tetris_index, name='tetris_index'),
]
