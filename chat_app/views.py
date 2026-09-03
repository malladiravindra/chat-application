from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, logout, authenticate
from django.contrib.auth.models import User
from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.contrib.auth.forms import AuthenticationForm
from .models import Message, UserProfile

def login_view(request):
    if request.user.is_authenticated:
        return redirect('chat_dashboard')

    if request.method == 'POST':
        form = AuthenticationForm(request, data=request.POST)
        if form.is_valid():
            user = form.get_user()
            login(request, user)
            
            profile, created = UserProfile.objects.get_or_create(user=user)
            profile.is_online = True
            profile.save()
            return redirect('chat_dashboard')
    else:
        form = AuthenticationForm()

    return render(request, 'chat_app/login.html', {'form': form})

def logout_view(request):
    if request.user.is_authenticated:
        try:
            profile = request.user.profile
            profile.is_online = False
            profile.save()
        except UserProfile.DoesNotExist:
            pass
        logout(request)
    return redirect('index')

@login_required(login_url='index')
def chat_dashboard_view(request):
    """Displays the single live group chat room with no sidebar."""
    current_user = request.user
    curr_profile, _ = UserProfile.objects.get_or_create(user=current_user)
    
    messages = Message.objects.filter(receiver__isnull=True).order_by('timestamp')
    
    context = {
        'current_user': current_user,
        'curr_profile': curr_profile,
        'messages': messages,
    }
    return render(request, 'chat_app/chat.html', context)

@login_required(login_url='index')
def chat_room_view(request, username):
    """Redirects to the main single live group chat dashboard."""
    return redirect('chat_dashboard')
