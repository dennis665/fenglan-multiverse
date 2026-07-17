from django.urls import path

from . import views

app_name = "line_manager"

urlpatterns = [
    #! LINE Webhook
    path("webhook/", views.line_webhook, name="line_webhook"),

    #! LIFF 網頁路由
    path("liff/", views.liff_itinerary_list, name="liff_itinerary_list"),
    path("liff/create/", views.liff_itinerary_create, name="liff_itinerary_create"),
    path("liff/bind/", views.liff_bind_account, name="liff_bind_account"),
    path("liff/drama/", views.liff_drama, name="liff_drama"),

    #! API 控制端點
    path("api/itineraries/", views.api_get_itineraries, name="api_get_itineraries"),
    path("api/itineraries/create/", views.api_create_itinerary, name="api_create_itinerary"),
    path("api/itineraries/delete/<int:pk>/", views.api_delete_itinerary, name="api_delete_itinerary"),
    path("api/itineraries/detail/<int:pk>/", views.api_get_itinerary_detail, name="api_get_itinerary_detail"),
    path("api/itineraries/update/<int:pk>/", views.api_update_itinerary, name="api_update_itinerary"),
    path("api/itineraries/hide/<int:pk>/", views.api_hide_itinerary, name="api_hide_itinerary"),
    path("api/itineraries/join/<int:pk>/", views.api_join_unscheduled_itinerary, name="api_join_unscheduled_itinerary"),
    path("api/itineraries/set_time/<int:pk>/", views.api_set_unscheduled_time, name="api_set_unscheduled_time"),
    path("api/itineraries/send_guide/", views.api_send_guide_message, name="api_send_guide_message"),
    path("api/bind/", views.api_bind_account, name="api_bind_account"),

    # 追劇與好友 API
    path("api/dramas/", views.api_get_dramas, name="api_get_dramas"),
    path("api/dramas/create/", views.api_create_drama, name="api_create_drama"),
    path("api/dramas/update_progress/<int:pk>/", views.api_update_drama_progress, name="api_update_drama_progress"),
    path("api/dramas/update/<int:pk>/", views.api_update_drama, name="api_update_drama"),
    path("api/dramas/recommend/", views.api_recommend_drama, name="api_recommend_drama"),
    path("api/dramas/accept_recommend/<int:pk>/", views.api_accept_recommendation, name="api_accept_recommendation"),
    path("api/dramas/search/", views.api_search_existing_dramas, name="api_search_existing_dramas"),
    path("api/dramas/join/<int:pk>/", views.api_join_drama, name="api_join_drama"),
    path("api/dramas/categories/", views.api_get_categories, name="api_get_categories"),
    path("api/friends/", views.api_get_friends, name="api_get_friends"),
    path("api/friends/add/", views.api_add_friend, name="api_add_friend"),

    # LINE 寵物系統 API 與頁面
    path("liff/pet/", views.liff_pet, name="liff_pet"),
    path("api/pet/status/", views.api_line_pet_status, name="api_line_pet_status"),
    path("api/pet/sync_steps/", views.api_line_pet_sync_steps, name="api_line_pet_sync_steps"),
    path("api/pet/buy_item/", views.api_line_pet_buy_item, name="api_line_pet_buy_item"),
    path("api/pet/use_item/", views.api_line_pet_use_item, name="api_line_pet_use_item"),
    path("api/pet/evolve/", views.api_line_pet_evolve, name="api_line_pet_evolve"),
    path("api/pet/switch_active/", views.api_line_pet_switch_active, name="api_line_pet_switch_active"),

    # Google Fit 步數綁定路由
    path("liff/pet/google/login/", views.liff_pet_google_login, name="liff_pet_google_login"),
    path("liff/pet/google/callback/", views.liff_pet_google_callback, name="liff_pet_google_callback"),
    path("api/pet/sync_google_fit/", views.api_line_pet_sync_google_fit, name="api_line_pet_sync_google_fit"),
    path("api/pet/unlink_google_fit/", views.api_line_pet_unlink_google_fit, name="api_line_pet_unlink_google_fit"),

    # 新增：每日登入、裝飾商城、派遣系統、爬塔闖關 API
    path("api/pet/claim_daily_login/", views.api_line_pet_claim_daily_login, name="api_line_pet_claim_daily_login"),
    path("api/pet/buy_accessory/", views.api_line_pet_buy_accessory, name="api_line_pet_buy_accessory"),
    path("api/pet/equip_accessory/", views.api_line_pet_equip_accessory, name="api_line_pet_equip_accessory"),
    path("api/pet/tower_battle/", views.api_line_pet_tower_battle, name="api_line_pet_tower_battle"),
    path("api/pet/start_expedition/", views.api_line_pet_start_expedition, name="api_line_pet_start_expedition"),
    path("api/pet/cancel_expedition/", views.api_line_pet_cancel_expedition, name="api_line_pet_cancel_expedition"),
    path("api/pet/claim_expedition/", views.api_line_pet_claim_expedition, name="api_line_pet_claim_expedition"),
    path("api/pet/claim_maintenance_gift/", views.api_line_pet_claim_maintenance_gift, name="api_line_pet_claim_maintenance_gift"),
]
