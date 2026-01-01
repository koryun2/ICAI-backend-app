from django.urls import path
from rest_framework_simplejwt.views import TokenRefreshView

from .views import (
    RegisterView,
    LoginView,
    MeView,
    InterviewSessionListCreateView,
    InterviewSessionDetailView,
    InterviewGenerateView,
    InterviewQuestionDetailView,
    InterviewEvaluateView,
)

urlpatterns = [
    path("auth/register/", RegisterView.as_view(), name="auth_register"),
    path("auth/login/", LoginView.as_view(), name="auth_login"),
    path("auth/token/refresh/", TokenRefreshView.as_view(), name="token_refresh"),
    path("user/", MeView.as_view(), name="user"),
    path("interviews/", InterviewSessionListCreateView.as_view()),
    path("interviews/<uuid:session_id>/", InterviewSessionDetailView.as_view()),
    path("interviews/<uuid:session_id>/generate/", InterviewGenerateView.as_view()),
    path(
        "interviews/<uuid:session_id>/questions/<int:order>/",
        InterviewQuestionDetailView.as_view(),
    ),
    path("interviews/<uuid:session_id>/evaluate/", InterviewEvaluateView.as_view()),
]
