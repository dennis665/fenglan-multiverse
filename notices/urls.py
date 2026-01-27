# notices/urls.py
from django.urls import path

from .views import NoticeDetailView, NoticeListView

app_name = "notices"  #! 命名空間，之後可以用 {% url 'notices:list' %}

urlpatterns = [
    path("", NoticeListView.as_view(), name="list"),
    path("<int:pk>/", NoticeDetailView.as_view(), name="detail"),
]
