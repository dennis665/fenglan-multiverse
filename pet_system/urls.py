from django.urls import path
from . import views

app_name = "pet_system"

urlpatterns = [
    path("dashboard/", views.pet_dashboard, name="dashboard"),
    path("api/get_dashboard_data/", views.api_get_dashboard_data, name="api_get_dashboard_data"),
    path("api/get_active_shimeji/", views.api_get_active_shimeji, name="api_get_active_shimeji"),
    path("api/claim_login_energy/", views.api_claim_login_energy, name="api_claim_login_energy"),
    path("api/hatch_egg/", views.api_hatch_egg, name="api_hatch_egg"),
    path("api/feed_pet/", views.api_feed_pet, name="api_feed_pet"),
    path("api/evolve_pet/", views.api_evolve_pet, name="api_evolve_pet"),
    path("api/rename_pet/", views.api_rename_pet, name="api_rename_pet"),
    path("api/switch_active_pet/", views.api_switch_active_pet, name="api_switch_active_pet"),
    path("api/get_story/", views.api_get_story, name="api_get_story"),
    path("api/start_expedition/", views.api_start_expedition, name="api_start_expedition"),
    path("api/claim_expedition_rewards/", views.api_claim_expedition_rewards, name="api_claim_expedition_rewards"),
    path("api/buy_accessory/", views.api_buy_accessory, name="api_buy_accessory"),
    path("api/equip_accessory/", views.api_equip_accessory, name="api_equip_accessory"),
    path("api/tower_battle_result/", views.api_tower_battle_result, name="api_tower_battle_result"),
]
