from django.urls import path
from rest_framework_simplejwt.views import TokenRefreshView

from .views import (
    RegisterView,
    LoginView,
    MeView,
    InterviewSessionListCreateView,
    InterviewSessionDetailView,
    InterviewAnswerView,
    InterviewGenerateView,
)

urlpatterns = [
    path("auth/register/", RegisterView.as_view(), name="auth_register"),
    path("auth/login/", LoginView.as_view(), name="auth_login"),
    path("auth/token/refresh/", TokenRefreshView.as_view(), name="token_refresh"),
    path("user/", MeView.as_view(), name="user"),
    path("interviews/", InterviewSessionListCreateView.as_view()),
    path("interviews/<uuid:session_id>/", InterviewSessionDetailView.as_view()),
    path("interviews/<uuid:session_id>/answer/", InterviewAnswerView.as_view()),
    path("interviews/<uuid:session_id>/generate/", InterviewGenerateView.as_view()),
]
