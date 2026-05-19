from django.urls import path

from . import views

urlpatterns = [
    path("create/", views.transfer_create, name="transfer_create"),
    path("reply/<int:record_id>/", views.transfer_reply, name="transfer_reply"),
    path("history/", views.transfer_history, name="transfer_history"),
    path("cancel/<int:record_id>/", views.transfer_cancel, name="transfer_cancel"),
]
