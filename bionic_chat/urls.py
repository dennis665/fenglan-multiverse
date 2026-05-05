from django.urls import path

from . import views

urlpatterns = [
    path("", views.chat_interface, name="chat_interface"),
    path("api/stream/", views.stream_llm_response, name="stream_llm_response"),
    path("api/translate/", views.translate_text_api, name="translate_text_api"),
    path("api/tts/", views.generate_audio_api, name="generate_audio_api"),
]
