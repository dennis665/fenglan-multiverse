from django.urls import path

from . import views

app_name = "media_studio"

urlpatterns = [
    path("studio/", views.media_studio_view, name="media_studio_index"),
]
