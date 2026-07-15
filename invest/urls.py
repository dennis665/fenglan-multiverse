from django.urls import path

from .views import (
    apply_ai_plan,
    generate_ai_plan,
    portfolio_dashboard,
    stock_history_api,
)

app_name = "invest"

urlpatterns = [
    path("dashboard/", portfolio_dashboard, name="dashboard"),
    path("ai-plan/", generate_ai_plan, name="ai_plan"),
    path("apply-ai-plan/", apply_ai_plan, name="apply_ai_plan"),
    path("api/history/<str:symbol>/", stock_history_api, name="stock_history_api"),
]
