from django.shortcuts import get_object_or_404

from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.accounts.permissions import (
    HasPermission,
    user_has_permission,
)
from apps.addresses.models import Address
from apps.shipping.models import ShippingMethod

from .models import Order
from .serializers import OrderSerializer
from .services import OrderService


class OrderViewSet(viewsets.ViewSet):
    """
    Les clients ne voient que leurs propres commandes.
    Les administrateurs voient toutes les commandes.
    """

    def get_permissions(self):
        if self.action in ["list", "retrieve"]:
            return [HasPermission("orders.view")()]

        if self.action == "create":
            return [HasPermission("orders.create")()]

        if self.action == "update_status":
            return [HasPermission("orders.update")()]

        # L'annulation vérifie la propriété et le statut
        # dans OrderService.
        return [IsAuthenticated()]

    def get_queryset(self):
        queryset = (
            Order.objects
            .prefetch_related("items")
            .select_related(
                "shipping_address",
                "delivery__shipping_method",
            )
        )

        if (
            self.request.user.is_staff
            or user_has_permission(
                self.request.user,
                "orders.update",
            )
        ):
            return queryset.all()

        return queryset.filter(user=self.request.user)

    def list(self, request):
        serializer = OrderSerializer(
            self.get_queryset(),
            many=True,
        )

        return Response(serializer.data)

    def retrieve(self, request, pk=None):
        order = get_object_or_404(
            self.get_queryset(),
            pk=pk,
        )

        serializer = OrderSerializer(order)

        return Response(serializer.data)

    def create(self, request):
        address_id = request.data.get("address_id")

        if not address_id:
            return Response(
                {
                    "address_id": (
                        "L'adresse de livraison est obligatoire."
                    )
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        address = get_object_or_404(
            Address,
            pk=address_id,
            user=request.user,
        )

        shipping_method = None
        shipping_method_id = request.data.get(
            "shipping_method_id"
        )

        if shipping_method_id:
            try:
                shipping_method = ShippingMethod.objects.get(
                    pk=shipping_method_id,
                    is_active=True,
                )
            except (
                ShippingMethod.DoesNotExist,
                TypeError,
                ValueError,
            ):
                return Response(
                    {
                        "shipping_method_id": (
                            "Mode de livraison introuvable "
                            "ou désactivé."
                        )
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )

        try:
            order = OrderService.create_order(
                user=request.user,
                address=address,
                shipping_method=shipping_method,
                notes=request.data.get("notes"),
                coupon_code=(
                    request.data.get("coupon_code")
                    or request.data.get("coupon")
                ),
            )

        except PermissionDenied as exc:
            return Response(
                {"detail": str(exc)},
                status=status.HTTP_403_FORBIDDEN,
            )

        except ValueError as exc:
            return Response(
                {"detail": str(exc)},
                status=status.HTTP_400_BAD_REQUEST,
            )

        serializer = OrderSerializer(order)

        return Response(
            serializer.data,
            status=status.HTTP_201_CREATED,
        )

    @action(
        detail=True,
        methods=["post"],
        url_path="cancel",
    )
    def cancel(self, request, pk=None):
        order = get_object_or_404(
            self.get_queryset(),
            pk=pk,
        )

        try:
            order = OrderService.cancel_order(
                order=order,
                actor=request.user,
            )

        except PermissionDenied as exc:
            return Response(
                {"detail": str(exc)},
                status=status.HTTP_403_FORBIDDEN,
            )

        except ValueError as exc:
            return Response(
                {"detail": str(exc)},
                status=status.HTTP_400_BAD_REQUEST,
            )

        serializer = OrderSerializer(order)

        return Response(serializer.data)

    @action(
        detail=True,
        methods=["patch"],
        url_path="status",
    )
    def update_status(self, request, pk=None):
        new_status = request.data.get("status")

        valid_statuses = {
            value
            for value, _label in Order.Status.choices
        }

        if new_status not in valid_statuses:
            return Response(
                {
                    "status": (
                        "Statut de commande invalide. "
                        f"Valeurs possibles : "
                        f"{', '.join(sorted(valid_statuses))}."
                    )
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        order = get_object_or_404(
            self.get_queryset(),
            pk=pk,
        )

        try:
            order = OrderService.update_status(
                order=order,
                new_status=new_status,
                actor=request.user,
            )

        except PermissionDenied as exc:
            return Response(
                {"detail": str(exc)},
                status=status.HTTP_403_FORBIDDEN,
            )

        except ValueError as exc:
            return Response(
                {"detail": str(exc)},
                status=status.HTTP_400_BAD_REQUEST,
            )

        serializer = OrderSerializer(order)

        return Response(serializer.data)
