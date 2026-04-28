from django.urls import path

from . import views

app_name = "sh_recognition"

urlpatterns = [
    path("", views.index, name="index"),
    path("list/", views.record_list, name="record_list"),  # * 清單頁
    path("detail/<int:pk>/", views.record_detail, name="record_detail"),  # * 詳情頁
]
