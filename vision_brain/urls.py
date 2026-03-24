from django.urls import path

from . import views

app_name = "vision_brain"

urlpatterns = [
    path("", views.ocr_recognize, name="recognize"),
]
