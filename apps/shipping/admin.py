from django.contrib import admin

from .models import (
    Delivery,
    ShippingMethod,
    ShippingRate,
    ShippingZone,
)


@admin.register(ShippingZone)
class ShippingZoneAdmin(admin.ModelAdmin):
    list_display = ["name", "is_active"]
    list_filter = ["is_active"]
    search_fields = ["name"]
    filter_horizontal = ["countries"]


@admin.register(ShippingMethod)
class ShippingMethodAdmin(admin.ModelAdmin):
    list_display = [
        "name",
        "code",
        "carrier",
        "estimated_days",
        "is_active",
    ]
    list_filter = ["is_active"]
    search_fields = ["name", "code", "carrier"]


@admin.register(ShippingRate)
class ShippingRateAdmin(admin.ModelAdmin):
    list_display = [
        "zone",
        "method",
        "min_weight_grams",
        "max_weight_grams",
        "price",
        "currency",
        "is_active",
    ]
    list_filter = ["is_active", "zone", "method", "currency"]
    search_fields = ["zone__name", "method__name"]


@admin.register(Delivery)
class DeliveryAdmin(admin.ModelAdmin):
    list_display = [
        "order",
        "shipping_method",
        "tracking_number",
        "status",
        "estimated_delivery_date",
    ]
    list_filter = ["status", "shipping_method"]
    search_fields = ["order__reference", "tracking_number"]
