from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import CustomUser, Message, OTPVerification


@admin.register(CustomUser)
class CustomUserAdmin(UserAdmin):
    model = CustomUser
    list_display  = ('phone_number', 'is_verified', 'is_active', 'is_staff', 'created_at')
    list_filter   = ('is_verified', 'is_active', 'is_staff')
    search_fields = ('phone_number',)
    ordering      = ('-created_at',)

    fieldsets = (
        (None,            {'fields': ('phone_number', 'password')}),
        ('Status',        {'fields': ('is_verified', 'is_active', 'is_online', 'avatar_color')}),
        ('Permissions',   {'fields': ('is_staff', 'is_superuser', 'groups', 'user_permissions')}),
        ('Dates',         {'fields': ('last_login', 'created_at', 'updated_at')}),
    )
    readonly_fields = ('created_at', 'updated_at', 'last_login')

    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('phone_number', 'password1', 'password2', 'is_verified', 'is_active', 'is_staff'),
        }),
    )


@admin.register(Message)
class MessageAdmin(admin.ModelAdmin):
    list_display  = ('sender', 'receiver', 'content', 'timestamp', 'is_read')
    list_filter   = ('is_read', 'timestamp')
    search_fields = ('sender__phone_number', 'content')


@admin.register(OTPVerification)
class OTPVerificationAdmin(admin.ModelAdmin):
    list_display  = ('phone_number', 'purpose', 'attempts', 'created_at')
    list_filter   = ('purpose',)
    search_fields = ('phone_number',)
