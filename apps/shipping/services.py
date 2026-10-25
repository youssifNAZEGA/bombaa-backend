from dataclasses import dataclass
from datetime import timedelta
from decimal import Decimal, ROUND_HALF_UP

from django.db.models import Q
from django.utils import timezone

from apps.geography.models import Country
from apps.geography.services import CurrencyService

from .models import (
    ShippingMethod,
    ShippingRate,
    ShippingZone,
)


MONEY_QUANTUM = Decimal("0.01")


@dataclass
class ShippingQuote:
    cost: Decimal
    currency: object
    method: ShippingMethod | None
    zone: ShippingZone | None
    estimated_days: int | None
    weight_grams: int


class ShippingService:

    @staticmethod
    def find_country(value):
        if value is None:
            return None

        value = str(value).strip()

        if not value:
            return None

        queryset = Country.objects.filter(is_active=True)

        if value.isdigit():
            country = queryset.filter(pk=int(value)).first()

            if country:
                return country

        return (
            queryset
            .filter(Q(code__iexact=value) | Q(name__iexact=value))
            .first()
        )

    @staticmethod
    def resolve_country(address):
        if address is None:
            return None

        if getattr(address, "country_ref_id", None):
            return address.country_ref

        return ShippingService.find_country(
            getattr(address, "country", None)
        )

    @staticmethod
    def zones_for_country(country):
        zones = ShippingZone.objects.filter(is_active=True)

        specific_zones = zones.filter(countries=country)

        if specific_zones.exists():
            return specific_zones

        return zones.filter(countries__isnull=True)

    @staticmethod
    def _zero_quote(country=None, weight_grams=0):
        currency = CurrencyService.base_currency()

        if currency is None and country is not None:
            currency = country.currency

        return ShippingQuote(
            cost=Decimal("0.00"),
            currency=currency,
            method=None,
            zone=None,
            estimated_days=None,
            weight_grams=max(int(weight_grams or 0), 0),
        )

    @staticmethod
    def _rate_cost(rate, base_currency):
        if (
            rate.currency is not None
            and base_currency is not None
            and rate.currency_id != base_currency.id
        ):
            return rate.currency.convert_to_base(rate.price)

        return Decimal(rate.price)

    @classmethod
    def quote(
        cls,
        *,
        country=None,
        method=None,
        weight_grams=0,
    ):
        weight_grams = max(int(weight_grams or 0), 0)

        if country is None:
            return cls._zero_quote(
                weight_grams=weight_grams,
            )

        zones = cls.zones_for_country(country)

        if not zones.exists():
            raise ValueError(
                f"Aucune zone de livraison n'est configurée "
                f"pour {country.name}."
            )

        rates = (
            ShippingRate.objects
            .filter(
                zone__in=zones,
                is_active=True,
                method__is_active=True,
                min_weight_grams__lte=weight_grams,
            )
            .filter(
                Q(max_weight_grams__isnull=True)
                | Q(max_weight_grams__gte=weight_grams)
            )
            .select_related(
                "zone",
                "method",
                "currency",
            )
        )

        if method is not None:
            rates = rates.filter(method=method)

        rates = list(rates)

        if not rates:
            method_label = (
                f" pour {method.name}" if method else ""
            )

            raise ValueError(
                "Aucun tarif de livraison n'est disponible"
                f"{method_label} pour {country.name} "
                f"avec un poids de {weight_grams} g."
            )

        base_currency = CurrencyService.base_currency()

        selected_rate = min(
            rates,
            key=lambda rate: cls._rate_cost(
                rate,
                base_currency,
            ),
        )

        cost = cls._rate_cost(
            selected_rate,
            base_currency,
        ).quantize(
            MONEY_QUANTUM,
            rounding=ROUND_HALF_UP,
        )

        return ShippingQuote(
            cost=cost,
            currency=(
                base_currency
                or selected_rate.currency
                or country.currency
            ),
            method=selected_rate.method,
            zone=selected_rate.zone,
            estimated_days=selected_rate.method.estimated_days,
            weight_grams=weight_grams,
        )

    @staticmethod
    def estimated_delivery_date(method):
        if method is None:
            return None

        return timezone.localdate() + timedelta(
            days=method.estimated_days or 0
        )
