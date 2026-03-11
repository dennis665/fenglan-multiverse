from django.urls import path

from . import views

app_name = "study_brain"

urlpatterns = [
    path("dashboard/", views.dashboard, name="dashboard"),
    path("upload/", views.upload_material, name="upload"),
    path("generate/<int:material_id>/", views.generate_analysis, name="generate"),
    path("room/<int:material_id>/", views.study_room, name="study_room"),
    path("quiz/submit/<int:analysis_id>/", views.submit_quiz, name="submit_quiz"),
    path("quiz/result/<int:record_id>/", views.quiz_result, name="quiz_result"),
    path("material/<int:material_id>/view/", views.view_material, name="view_material"),
    path("material/<int:material_id>/toggle/<str:action>/", views.toggle_save_material, name="toggle_save"),
    path("history/", views.quiz_history_list, name="quiz_history"),
]
