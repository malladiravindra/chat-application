from django.urls import path
from . import views
from . import api_views

urlpatterns = [
    # ── Page Views ──────────────────────────────────────
    path('',                 views.login_view,          name='index'),
    path('register/',        views.register_view,        name='register'),
    path('forgot-password/', views.forgot_password_view, name='forgot_password'),
    path('logout/',          views.logout_view,          name='logout'),
    path('chat/',            views.chat_dashboard_view,  name='chat_dashboard'),
    path('chat/<str:phone>/', views.chat_room_view,      name='chat_room'),

    # ── Auth API Endpoints ───────────────────────────────
    path('api/auth/register/',        api_views.RegisterView.as_view(),       name='api_register'),
    path('api/auth/send-otp/',        api_views.SendOTPView.as_view(),        name='api_send_otp'),
    path('api/auth/verify-otp/',      api_views.VerifyOTPView.as_view(),      name='api_verify_otp'),
    path('api/auth/login/',           api_views.LoginView.as_view(),          name='api_login'),
    path('api/auth/forgot-password/', api_views.ForgotPasswordView.as_view(), name='api_forgot_password'),
    path('api/auth/reset-password/',  api_views.ResetPasswordView.as_view(),  name='api_reset_password'),
]
