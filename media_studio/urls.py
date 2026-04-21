from django.urls import path

from . import views

app_name = "media_studio"

urlpatterns = [
    path("compressor/", views.image_compressor_view, name="image_compressor"),
]
