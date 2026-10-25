from django.contrib import admin

from .models import AuditLog


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):

    list_display = (
        "created_at",
        "action",
        "actor_email",
        "target_type",
        "target_repr",
    )

    list_filter = (
        "action",
        "target_type",
    )

    search_fields = (
        "actor_email",
        "target_repr",
        "target_id",
    )

    readonly_fields = (
        "actor",
        "actor_email",
        "action",
        "target_type",
        "target_id",
        "target_repr",
        "changes",
        "metadata",
        "ip_address",
        "user_agent",
        "created_at",
    )

    ordering = ("-created_at",)

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
