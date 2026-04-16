#! 遊戲中心路由
from django.urls import path

from . import views

app_name = "games"

urlpatterns = [
    #! 遊戲大廳
    path("", views.lobby_index, name="lobby_index"),
    #! 倖存者生存遊戲
    path("survivor/", views.survivor_index, name="survivor_index"),
    path("api/survivor/save/", views.survivor_save_api, name="survivor_save_api"),
    path("api/survivor/upgrade/", views.buy_upgrade_api, name="buy_upgrade_api"),
    #! 虛擬人生遊戲
    path("virtual-life/", views.virtual_life_index, name="virtual_life_index"),
    path("api/virtual-life/save/", views.vl_save_api, name="vl_save_api"),
    #! 魔塔路由
    path("magictower/", views.mt_index, name="mt_index"),
    path("api/magictower/save/", views.mt_save_api, name="mt_save_api"),
    path("api/magictower/reward/", views.mt_reward_api, name="mt_reward_api"),
    path("api/magictower/reset/", views.mt_reset_api, name="mt_reset_api"),
]
