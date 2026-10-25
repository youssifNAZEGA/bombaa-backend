from django.contrib import admin

from .models import Notification, NotificationPreference


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = [
        "title",
        "user",
        "event",
        "channel",
        "is_read",
        "created_at",
    ]
    list_filter = [
        "event",
        "channel",
        "is_read",
    ]
    search_fields = [
        "title",
        "message",
        "user__email",
    ]
    readonly_fields = [
        "created_at",
        "read_at",
    ]


@admin.register(NotificationPreference)
class NotificationPreferenceAdmin(admin.ModelAdmin):
    list_display = [
        "user",
        "in_app_enabled",
        "email_enabled",
        "sms_enabled",
        "push_enabled",
        "updated_at",
    ]
    search_fields = ["user__email"]
