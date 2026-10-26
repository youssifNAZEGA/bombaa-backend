from django.contrib import admin

from .models import (
    FaqEntry,
    SupportEvent,
    SupportMessage,
    SupportTicket,
)


class SupportMessageInline(admin.TabularInline):
    model = SupportMessage
    extra = 0
    readonly_fields = [
        "author",
        "author_name",
        "author_email",
        "created_at",
    ]


class SupportEventInline(admin.TabularInline):
    model = SupportEvent
    extra = 0
    readonly_fields = [
        "action",
        "actor",
        "actor_name",
        "previous_status",
        "new_status",
        "note",
        "created_at",
    ]
    can_delete = False


@admin.register(FaqEntry)
class FaqEntryAdmin(admin.ModelAdmin):
    list_display = [
        "question",
        "category",
        "display_order",
        "is_active",
    ]
    list_filter = [
        "is_active",
        "category",
    ]
    search_fields = [
        "question",
        "answer",
    ]
    ordering = [
        "display_order",
        "id",
    ]


@admin.register(SupportTicket)
class SupportTicketAdmin(admin.ModelAdmin):
    list_display = [
        "reference",
        "subject",
        "type",
        "status",
        "priority",
        "contact_email",
        "assigned_to",
        "created_at",
    ]
    list_filter = [
        "type",
        "status",
        "priority",
        "assigned_to",
    ]
    search_fields = [
        "reference",
        "subject",
        "description",
        "contact_name",
        "contact_email",
        "contact_phone",
        "order__reference",
    ]
    readonly_fields = [
        "reference",
        "created_at",
        "updated_at",
    ]
    inlines = [
        SupportMessageInline,
        SupportEventInline,
    ]


@admin.register(SupportMessage)
class SupportMessageAdmin(admin.ModelAdmin):
    list_display = [
        "ticket",
        "author_name",
        "is_internal",
        "created_at",
    ]
    list_filter = [
        "is_internal",
    ]
    search_fields = [
        "ticket__reference",
        "author_name",
        "author_email",
        "body",
    ]
    readonly_fields = [
        "created_at",
    ]


@admin.register(SupportEvent)
class SupportEventAdmin(admin.ModelAdmin):
    list_display = [
        "ticket",
        "action",
        "actor_name",
        "previous_status",
        "new_status",
        "created_at",
    ]
    list_filter = [
        "action",
    ]
    search_fields = [
        "ticket__reference",
        "actor_name",
        "note",
    ]
    readonly_fields = [
        "created_at",
    ]
