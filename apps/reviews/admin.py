from django.contrib import admin

from .models import Review, ReviewImage


class ReviewImageInline(admin.TabularInline):
    model = ReviewImage
    extra = 0
    readonly_fields = ["created_at"]


@admin.register(Review)
class ReviewAdmin(admin.ModelAdmin):
    list_display = [
        "product",
        "user",
        "rating",
        "status",
        "is_verified_purchase",
        "created_at",
    ]
    list_filter = [
        "status",
        "rating",
        "is_verified_purchase",
    ]
    search_fields = [
        "product__name",
        "user__email",
        "comment",
    ]
    readonly_fields = [
        "created_at",
        "updated_at",
        "moderated_at",
    ]
    inlines = [ReviewImageInline]


@admin.register(ReviewImage)
class ReviewImageAdmin(admin.ModelAdmin):
    list_display = [
        "review",
        "image_url",
        "created_at",
    ]
    search_fields = [
        "review__product__name",
        "review__user__email",
        "alt_text",
    ]
    readonly_fields = ["created_at"]
