from django.contrib import admin

from .models import Refund, ReturnItem, ReturnRequest


class ReturnItemInline(admin.TabularInline):
    model = ReturnItem
    extra = 0
    readonly_fields = [
        "order_item",
        "product_name",
        "sku",
        "unit_price",
        "subtotal",
        "created_at",
    ]


@admin.register(ReturnRequest)
class ReturnRequestAdmin(admin.ModelAdmin):
    list_display = [
        "reference",
        "order",
        "status",
        "total_amount",
        "currency",
        "processed_by",
        "created_at",
    ]
    list_filter = [
        "status",
        "currency",
    ]
    search_fields = [
        "reference",
        "order__reference",
        "reason",
        "order__user__email",
    ]
    readonly_fields = [
        "reference",
        "total_amount",
        "currency",
        "created_at",
        "updated_at",
    ]
    inlines = [ReturnItemInline]


@admin.register(ReturnItem)
class ReturnItemAdmin(admin.ModelAdmin):
    list_display = [
        "return_request",
        "sku",
        "quantity",
        "subtotal",
    ]
    search_fields = [
        "return_request__reference",
        "sku",
        "product_name",
    ]
    readonly_fields = ["created_at"]


@admin.register(Refund)
class RefundAdmin(admin.ModelAdmin):
    list_display = [
        "reference",
        "order",
        "amount",
        "currency",
        "method",
        "status",
        "processed_by",
        "requested_at",
    ]
    list_filter = [
        "status",
        "method",
        "currency",
    ]
    search_fields = [
        "reference",
        "order__reference",
        "external_reference",
        "reason",
        "order__user__email",
    ]
    readonly_fields = [
        "reference",
        "currency",
        "requested_at",
        "updated_at",
    ]
