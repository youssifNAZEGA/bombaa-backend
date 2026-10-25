from django.db.models import Q

from rest_framework import status, viewsets
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.permissions import HasPermission, user_has_permission
from apps.geography.serializers import CountrySummarySerializer

from .models import (
    Delivery,
    ShippingMethod,
    ShippingRate,
    ShippingZone,
)
from .serializers import (
    DeliverySerializer,
    ShippingMethodSerializer,
    ShippingRateSerializer,
    ShippingZoneSerializer,
)
from .services import ShippingService


def can_manage_shipping(user):
    if not user or not user.is_authenticated:
        return False

    return user.is_staff or user_has_permission(
        user,
        "shipping.update",
    )


class ShippingZoneViewSet(viewsets.ModelViewSet):

    serializer_class = ShippingZoneSerializer

    def get_queryset(self):
        queryset = (
            ShippingZone.objects
            .prefetch_related("countries")
        )

        if not can_manage_shipping(self.request.user):
            queryset = queryset.filter(is_active=True)

        search = self.request.query_params.get("search")

        if search:
            queryset = queryset.filter(name__icontains=search)

        country_value = self.request.query_params.get("country")

        if country_value:
            country = ShippingService.find_country(country_value)

            if country is None:
                return queryset.none()

            zones = ShippingService.zones_for_country(country)

            queryset = queryset.filter(
                pk__in=zones.values("pk")
            )

        return queryset

    def get_permissions(self):
        if self.action in ["list", "retrieve"]:
            return [AllowAny()]

        if self.action == "create":
            permission = "shipping.create"

        elif self.action in ["update", "partial_update"]:
            permission = "shipping.update"

        elif self.action == "destroy":
            permission = "shipping.delete"

        else:
            permission = "shipping.view"

        return [HasPermission(permission)()]


class ShippingMethodViewSet(viewsets.ModelViewSet):

    serializer_class = ShippingMethodSerializer

    def get_queryset(self):
        queryset = ShippingMethod.objects.all()

        if not can_manage_shipping(self.request.user):
            queryset = queryset.filter(is_active=True)

        search = self.request.query_params.get("search")

        if search:
            queryset = queryset.filter(
                Q(name__icontains=search)
                | Q(code__icontains=search)
            )

        return queryset

    def get_permissions(self):
        if self.action in ["list", "retrieve"]:
            return [AllowAny()]

        if self.action == "create":
            permission = "shipping.create"

        elif self.action in ["update", "partial_update"]:
            permission = "shipping.update"

        elif self.action == "destroy":
            permission = "shipping.delete"

        else:
            permission = "shipping.view"

        return [HasPermission(permission)()]


class ShippingRateViewSet(viewsets.ModelViewSet):

    serializer_class = ShippingRateSerializer

    def get_queryset(self):
        queryset = (
            ShippingRate.objects
            .select_related(
                "zone",
                "method",
                "currency",
            )
        )

        if not can_manage_shipping(self.request.user):
            queryset = queryset.filter(
                is_active=True,
                zone__is_active=True,
                method__is_active=True,
            )

        country_value = self.request.query_params.get("country")

        if country_value:
            country = ShippingService.find_country(country_value)

            if country is None:
                return queryset.none()

            zones = ShippingService.zones_for_country(country)

            queryset = queryset.filter(zone__in=zones)

        weight_value = self.request.query_params.get("weight_grams")

        if weight_value is not None:
            try:
                weight_grams = int(weight_value)
            except (TypeError, ValueError):
                return queryset.none()

            if weight_grams < 0:
                return queryset.none()

            queryset = queryset.filter(
                min_weight_grams__lte=weight_grams
            ).filter(
                Q(max_weight_grams__isnull=True)
                | Q(max_weight_grams__gte=weight_grams)
            )

        method_value = self.request.query_params.get("method")

        if method_value:
            method_value = str(method_value).strip()

            if method_value.isdigit():
                queryset = queryset.filter(
                    method_id=int(method_value)
                )
            else:
                queryset = queryset.filter(
                    method__code__iexact=method_value
                )

        zone_value = self.request.query_params.get("zone")

        if zone_value:
            if not str(zone_value).isdigit():
                return queryset.none()

            queryset = queryset.filter(zone_id=int(zone_value))

        return queryset

    def get_permissions(self):
        if self.action in ["list", "retrieve"]:
            return [AllowAny()]

        if self.action == "create":
            permission = "shipping.create"

        elif self.action in ["update", "partial_update"]:
            permission = "shipping.update"

        elif self.action == "destroy":
            permission = "shipping.delete"

        else:
            permission = "shipping.view"

        return [HasPermission(permission)()]


class DeliveryViewSet(viewsets.ModelViewSet):

    serializer_class = DeliverySerializer

    def get_queryset(self):
        queryset = (
            Delivery.objects
            .select_related(
                "order",
                "shipping_method",
            )
        )

        if not can_manage_shipping(self.request.user):
            queryset = queryset.filter(
                order__user=self.request.user
            )

        order_value = self.request.query_params.get("order")

        if order_value:
            if not str(order_value).isdigit():
                return queryset.none()

            queryset = queryset.filter(order_id=int(order_value))

        delivery_status = self.request.query_params.get("status")

        if delivery_status:
            valid_statuses = {
                value
                for value, _label in Delivery.Status.choices
            }

            if delivery_status not in valid_statuses:
                return queryset.none()

            queryset = queryset.filter(status=delivery_status)

        return queryset

    def get_permissions(self):
        if self.action in ["list", "retrieve"]:
            return [IsAuthenticated()]

        return [HasPermission("shipping.update")()]


class ShippingQuoteView(APIView):

    permission_classes = [AllowAny]

    def get(self, request):
        country_value = request.query_params.get("country")

        if not country_value:
            return Response(
                {"country": "Le pays est obligatoire."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        country = ShippingService.find_country(country_value)

        if country is None:
            return Response(
                {"country": "Pays introuvable."},
                status=status.HTTP_404_NOT_FOUND,
            )

        weight_value = request.query_params.get(
            "weight_grams",
            "0",
        )

        try:
            weight_grams = int(weight_value)
        except (TypeError, ValueError):
            return Response(
                {"weight_grams": "Le poids est invalide."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if weight_grams < 0:
            return Response(
                {"weight_grams": "Le poids ne peut pas être négatif."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        method = None
        method_value = request.query_params.get("method")

        if method_value:
            method_value = str(method_value).strip()

            methods = ShippingMethod.objects.filter(
                is_active=True
            )

            if method_value.isdigit():
                method = methods.filter(
                    pk=int(method_value)
                ).first()
            else:
                method = methods.filter(
                    code__iexact=method_value
                ).first()

            if method is None:
                return Response(
                    {"method": "Mode de livraison introuvable."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

        try:
            quote = ShippingService.quote(
                country=country,
                method=method,
                weight_grams=weight_grams,
            )

        except ValueError as exc:
            return Response(
                {"detail": str(exc)},
                status=status.HTTP_400_BAD_REQUEST,
            )

        return Response({
            "country": CountrySummarySerializer(country).data,
            "weight_grams": quote.weight_grams,
            "shipping_cost": str(quote.cost),
            "currency": (
                quote.currency.code
                if quote.currency is not None
                else None
            ),
            "estimated_days": quote.estimated_days,
            "method": (
                ShippingMethodSerializer(quote.method).data
                if quote.method is not None
                else None
            ),
            "zone": (
                ShippingZoneSerializer(quote.zone).data
                if quote.zone is not None
                else None
            ),
        })
