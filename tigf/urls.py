from django.urls import path

from . import views

app_name = "tigf"

urlpatterns = [
    path("ics-merger/", views.ics_merger_dashboard, name="ics_merger_dashboard"),
    path("ics-merger/download/", views.download_merged_ics, name="download_merged_ics"),
    path("ics-cleaner/", views.ics_cleaner_dashboard, name="ics_cleaner_dashboard"),
    path("ics-cleaner/download/", views.download_cleaned_ics, name="download_cleaned_ics"),
    path("ics-validator/", views.ics_validator_dashboard, name="ics_validator_dashboard"),
]
