from django.contrib import admin

from .models import Country, Currency


@admin.register(Currency)
class CurrencyAdmin(admin.ModelAdmin):
    list_display = [
        "code",
        "name",
        "symbol",
        "exchange_rate",
        "is_base",
        "is_active",
    ]
    list_filter = ["is_base", "is_active"]
    search_fields = ["code", "name"]


@admin.register(Country)
class CountryAdmin(admin.ModelAdmin):
    list_display = [
        "name",
        "code",
        "currency",
        "phone_code",
        "is_active",
    ]
    list_filter = ["is_active", "currency"]
    search_fields = ["name", "code"]
    filter_horizontal = ["payment_methods"]
