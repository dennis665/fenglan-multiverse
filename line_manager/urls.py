from django.urls import path

from . import views

app_name = "line_manager"

urlpatterns = [
    path('api/pet/claim_broadcast_gift/', views.api_line_pet_claim_broadcast_gift, name='api_line_pet_claim_broadcast_gift'),
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
    path("api/dramas/reject_recommend/<int:pk>/", views.api_reject_recommendation, name="api_reject_recommendation"),
    path("api/dramas/ignore_recommend/<int:pk>/", views.api_ignore_recommendation, name="api_ignore_recommendation"),
    path("api/dramas/batch_recommend_action/", views.api_batch_recommend_action, name="api_batch_recommend_action"),
    path("api/dramas/check_friend_status/", views.api_check_friend_drama_status, name="api_check_friend_drama_status"),
    path("api/dramas/search/", views.api_search_existing_dramas, name="api_search_existing_dramas"),
    path("api/dramas/join/<int:pk>/", views.api_join_drama, name="api_join_drama"),
    path("api/dramas/remove/<int:pk>/", views.api_remove_drama, name="api_remove_drama"),
    path("api/dramas/categories/", views.api_get_categories, name="api_get_categories"),
    path("api/dramas/franchises/", views.api_get_franchises, name="api_get_franchises"),
    path("api/dramas/franchise_batch_track/", views.api_franchise_batch_track, name="api_franchise_batch_track"),
    path("api/dramas/compare_friends/", views.api_compare_friends, name="api_compare_friends"),
    path("api/dramas/github_media_list/", views.api_github_media_list, name="api_github_media_list"),
    path("api/dramas/download_media/", views.api_download_media, name="api_download_media"),
    path("api/dramas/batch_save_github_links/", views.api_batch_save_github_links, name="api_batch_save_github_links"),
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
    # FDA 食品營養成分資料庫 API 與頁面
    path("liff/nutrition/", views.liff_nutrition, name="liff_nutrition"),
    path("api/nutrition/all/", views.api_get_fda_nutrition_list, name="api_get_fda_nutrition_list"),
    path("api/nutrition/detail/<int:pk>/", views.api_get_fda_nutrition_detail, name="api_get_fda_nutrition_detail"),
    path("api/nutrition/references/", views.api_get_nutrient_references, name="api_get_nutrient_references"),
    path("api/nutrition/update_fda/", views.api_update_fda_nutrition, name="api_update_fda_nutrition"),

    # 每日飲食紀錄與一鍵健康分析 API
    path("api/nutrition/intake/add/", views.api_add_intake_log, name="api_add_intake_log"),
    path("api/nutrition/intake/list/", views.api_get_intake_logs, name="api_get_intake_logs"),
    path("api/nutrition/intake/delete/<int:log_id>/", views.api_delete_intake_log, name="api_delete_intake_log"),
    path("api/nutrition/intake/analyze/", views.api_analyze_daily_intake, name="api_analyze_daily_intake"),

    # 食品添加物與危害知識庫 API
    path("api/nutrition/additives/all/", views.api_get_food_additives, name="api_get_food_additives"),

    # 巴哈姆特 GNN 新聞與多標籤檢索 API
    path("gnn/", views.liff_gnn, name="liff_gnn"),
    path("api/gnn/list/", views.api_get_gnn_news, name="api_get_gnn_news"),
    path("api/gnn/crawl/", views.api_trigger_gnn_crawl, name="api_trigger_gnn_crawl"),

    # 手帳筆記本 (Planner Notebook) API
    path("api/planner/get/", views.api_get_planner_note, name="api_get_planner_note"),
    path("api/planner/save/", views.api_save_planner_note, name="api_save_planner_note"),
    path("api/planner/sync_today_itineraries/", views.api_sync_planner_itineraries, name="api_sync_planner_itineraries"),

    # 輕小說瀏覽器 (Novel Reader) LIFF 與 API 路由
    path("liff/novel/", views.liff_novel, name="liff_novel"),
    path("api/novel/list/", views.api_novel_list, name="api_novel_list"),
    path("api/novel/search/", views.api_novel_search, name="api_novel_search"),
    path("api/novel/import/", views.api_novel_import, name="api_novel_import"),
    path("api/novel/<str:novel_id>/catalog/", views.api_novel_catalog, name="api_novel_catalog"),
    path("api/novel/<str:novel_id>/chapter/<str:chapter_id>/", views.api_novel_chapter, name="api_novel_chapter"),
    path("api/novel/progress/save/", views.api_novel_progress_save, name="api_novel_progress_save"),
    path("api/novel/<str:novel_id>/delete/", views.api_novel_delete, name="api_novel_delete"),
    path("api/novel/<str:novel_id>/refresh/", views.api_novel_refresh, name="api_novel_refresh"),
    path("api/novel/proxy_image/", views.api_novel_proxy_image, name="api_novel_proxy_image"),
    path("api/novel/run_python/", views.api_novel_run_python, name="api_novel_run_python"),
]

