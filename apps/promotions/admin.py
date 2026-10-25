from django.contrib import admin

from .models import Coupon, CouponRedemption, Promotion


@admin.register(Promotion)
class PromotionAdmin(admin.ModelAdmin):
    list_display = [
        "name",
        "discount_type",
        "value",
        "is_active",
        "starts_at",
        "ends_at",
        "created_at",
    ]
    list_filter = [
        "discount_type",
        "is_active",
    ]
    search_fields = [
        "name",
        "description",
    ]
    filter_horizontal = [
        "products",
        "categories",
        "brands",
        "countries",
    ]
    readonly_fields = [
        "created_at",
        "updated_at",
    ]


@admin.register(Coupon)
class CouponAdmin(admin.ModelAdmin):
    list_display = [
        "code",
        "discount_type",
        "value",
        "minimum_amount",
        "max_uses",
        "is_active",
        "starts_at",
        "ends_at",
        "created_at",
    ]
    list_filter = [
        "discount_type",
        "is_active",
    ]
    search_fields = [
        "code",
        "description",
    ]
    filter_horizontal = [
        "products",
        "categories",
        "countries",
    ]
    readonly_fields = [
        "created_at",
        "updated_at",
    ]


@admin.register(CouponRedemption)
class CouponRedemptionAdmin(admin.ModelAdmin):
    list_display = [
        "coupon",
        "user",
        "order",
        "discount_amount",
        "created_at",
        "released_at",
    ]
    list_filter = [
        "coupon",
    ]
    search_fields = [
        "coupon__code",
        "order__reference",
        "user__email",
    ]
    readonly_fields = [
        "created_at",
    ]
