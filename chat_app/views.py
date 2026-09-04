from django.shortcuts import render, redirect
from django.contrib.auth import get_user_model, logout
from django.contrib.auth.decorators import login_required
from .models import Message

User = get_user_model()


def login_view(request):
    """Renders the phone-number + password login page."""
    if request.user.is_authenticated:
        return redirect('chat_dashboard')
    return render(request, 'chat_app/login.html')


def register_view(request):
    """Renders the registration page (phone + password + OTP verify)."""
    if request.user.is_authenticated:
        return redirect('chat_dashboard')
    return render(request, 'chat_app/register.html')


def forgot_password_view(request):
    """Renders the forgot-password / reset-password page."""
    return render(request, 'chat_app/forgot_password.html')


def logout_view(request):
    """Logs the user out and marks them offline."""
    if request.user.is_authenticated:
        user = request.user
        user.is_online = False
        user.save(update_fields=['is_online'])
        logout(request)
    return redirect('index')


@login_required(login_url='index')
def chat_dashboard_view(request):
    """Displays the live group chat room."""
    current_user = request.user
    messages = Message.objects.filter(receiver__isnull=True).order_by('timestamp')

    context = {
        'current_user': current_user,
        'messages': messages,
    }
    return render(request, 'chat_app/chat.html', context)


@login_required(login_url='index')
def chat_room_view(request, phone):
    """Redirects to the main single live group chat dashboard."""
    return redirect('chat_dashboard')
