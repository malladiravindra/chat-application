from django.urls import path
from . import views

urlpatterns = [
    path('', views.login_view, name='index'),
    path('logout/', views.logout_view, name='logout'),
    path('chat/', views.chat_dashboard_view, name='chat_dashboard'),
    path('chat/<str:username>/', views.chat_room_view, name='chat_room'),
]
