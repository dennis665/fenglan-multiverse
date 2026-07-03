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

    #! API 控制端點
    path("api/itineraries/", views.api_get_itineraries, name="api_get_itineraries"),
    path("api/itineraries/create/", views.api_create_itinerary, name="api_create_itinerary"),
    path("api/itineraries/delete/<int:pk>/", views.api_delete_itinerary, name="api_delete_itinerary"),
    path("api/bind/", views.api_bind_account, name="api_bind_account"),
]
