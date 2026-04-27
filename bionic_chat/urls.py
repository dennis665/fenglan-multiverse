from django.urls import path

from . import views

urlpatterns = [
    path("", views.chat_interface, name="chat_interface"),
    path("api/stream/", views.stream_llm_response, name="stream_llm_response"),
]
