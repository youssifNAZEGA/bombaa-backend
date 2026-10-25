from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

from django.db.models import Q

from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from apps.accounts.permissions import HasPermission, user_has_permission

from .models import Country, Currency
from .serializers import (
    CountrySerializer,
    CurrencySerializer,
)
from .services import CurrencyService


def can_manage_geography(user, permission="countries.update"):
    if not user or not user.is_authenticated:
        return False

    return user.is_staff or user_has_permission(user, permission)


class CurrencyViewSet(viewsets.ModelViewSet):

    serializer_class = CurrencySerializer

    def get_queryset(self):
        queryset = Currency.objects.all()

        if not can_manage_geography(
            self.request.user,
            "currencies.update",
        ):
            queryset = queryset.filter(is_active=True)

        return queryset

    def get_permissions(self):
        if self.action in ["list", "retrieve", "convert"]:
            return [AllowAny()]

        if self.action == "create":
            permission = "currencies.create"

        elif self.action in ["update", "partial_update"]:
            permission = "currencies.update"

        elif self.action == "destroy":
            permission = "currencies.delete"

        else:
            permission = "currencies.view"

        return [HasPermission(permission)()]

    @action(
        detail=False,
        methods=["get"],
        url_path="convert",
    )
    def convert(self, request):
        amount_value = request.query_params.get("amount")

        if amount_value is None:
            return Response(
                {"amount": "Le montant est obligatoire."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            amount = Decimal(amount_value)
        except (InvalidOperation, TypeError, ValueError):
            return Response(
                {"amount": "Le montant est invalide."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if not amount.is_finite() or amount < 0:
            return Response(
                {"amount": "Le montant est invalide."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        base_currency = CurrencyService.base_currency()

        source = base_currency

        if request.query_params.get("from"):
            source = CurrencyService.get_active_currency(
                request.query_params["from"]
            )

            if source is None:
                return Response(
                    {"from": "Devise source introuvable."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

        target = base_currency

        if request.query_params.get("to"):
            target = CurrencyService.get_active_currency(
                request.query_params["to"]
            )

            if target is None:
                return Response(
                    {"to": "Devise cible introuvable."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

        if source is None or target is None:
            return Response(
                {
                    "detail": (
                        "Aucune devise active n'est configurée."
                    )
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        converted_amount = CurrencyService.convert(
            amount,
            source,
            target,
        )

        rate = (
            source.exchange_rate / target.exchange_rate
        ).quantize(
            Decimal("0.000001"),
            rounding=ROUND_HALF_UP,
        )

        return Response({
            "amount": str(amount),
            "from": source.code,
            "to": target.code,
            "converted_amount": str(converted_amount),
            "rate": str(rate),
        })


class CountryViewSet(viewsets.ModelViewSet):

    serializer_class = CountrySerializer

    def get_queryset(self):
        queryset = (
            Country.objects
            .select_related("currency")
            .prefetch_related("payment_methods")
        )

        if not can_manage_geography(self.request.user):
            queryset = queryset.filter(is_active=True)

        search = self.request.query_params.get("search")

        if search:
            queryset = queryset.filter(
                Q(name__icontains=search)
                | Q(code__icontains=search)
            )

        currency = self.request.query_params.get("currency")

        if currency:
            queryset = queryset.filter(
                currency__code__iexact=currency
            )

        return queryset

    def get_permissions(self):
        if self.action in ["list", "retrieve"]:
            return [AllowAny()]

        if self.action == "create":
            permission = "countries.create"

        elif self.action in ["update", "partial_update"]:
            permission = "countries.update"

        elif self.action == "destroy":
            permission = "countries.delete"

        else:
            permission = "countries.view"

        return [HasPermission(permission)()]
