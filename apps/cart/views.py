from django.db import transaction
from django.shortcuts import get_object_or_404

from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.catalog.models import ProductVariant
from apps.promotions.services import (
    CouponService,
    PricingService,
)
from apps.shipping.services import ShippingService

from .models import Cart, CartItem
from .serializers import CartItemSerializer, CartSerializer


class CartViewSet(viewsets.ViewSet):
    permission_classes = [IsAuthenticated]

    def get_cart(self, user):
        cart, _ = Cart.objects.get_or_create(
            user=user
        )
        return cart

    def get_country(self, request):
        value = request.query_params.get("country")

        if value:
            return ShippingService.find_country(value)

        addresses = (
            request.user.addresses
            .select_related("country_ref")
            .order_by("-is_default", "-created_at")
        )

        address = addresses.first()

        if address is None:
            return None

        if address.country_ref_id:
            return address.country_ref

        return ShippingService.find_country(address.country)

    def get_cart_for_response(self, cart):
        return (
            Cart.objects
            .select_related("coupon")
            .prefetch_related(
                "items__variant__product",
                (
                    "items__variant__product"
                    "__product_categories"
                ),
            )
            .get(pk=cart.pk)
        )

    def cart_response(self, request, cart):
        cart = self.get_cart_for_response(cart)

        serializer = CartSerializer(
            cart,
            context={
                "request": request,
                "country": self.get_country(request),
            },
        )

        return Response(serializer.data)

    def list(self, request):
        cart = self.get_cart(request.user)

        return self.cart_response(request, cart)

    @action(
        detail=False,
        methods=["post"],
        url_path="items",
    )
    @transaction.atomic
    def add_item(self, request):
        variant_id = request.data.get("variant")
        quantity = request.data.get("quantity", 1)

        if not variant_id:
            return Response(
                {
                    "variant": (
                        "La variante est obligatoire."
                    )
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            quantity = int(quantity)
        except (TypeError, ValueError):
            return Response(
                {
                    "quantity": (
                        "La quantité doit être un entier."
                    )
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        if quantity <= 0:
            return Response(
                {
                    "quantity": (
                        "La quantité doit être supérieure à 0."
                    )
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        variant = get_object_or_404(
            ProductVariant,
            pk=variant_id,
            is_active=True,
        )

        cart = self.get_cart(request.user)

        item, created = CartItem.objects.get_or_create(
            cart=cart,
            variant=variant,
            defaults={
                "quantity": quantity,
            },
        )

        if not created:
            item.quantity += quantity
            item.save(
                update_fields=[
                    "quantity",
                    "updated_at",
                ]
            )

        serializer = CartItemSerializer(item)

        return Response(
            serializer.data,
            status=(
                status.HTTP_201_CREATED
                if created
                else status.HTTP_200_OK
            ),
        )

    @action(
        detail=False,
        methods=["patch"],
        url_path=r"items/(?P<item_id>\d+)",
    )
    @transaction.atomic
    def update_item(self, request, item_id=None):
        cart = self.get_cart(request.user)

        item = get_object_or_404(
            CartItem,
            pk=item_id,
            cart=cart,
        )

        quantity = request.data.get("quantity")

        if quantity is None:
            return Response(
                {
                    "quantity": (
                        "La quantité est obligatoire."
                    )
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            quantity = int(quantity)
        except (TypeError, ValueError):
            return Response(
                {
                    "quantity": (
                        "La quantité doit être un entier."
                    )
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        if quantity <= 0:
            return Response(
                {
                    "quantity": (
                        "La quantité doit être supérieure à 0."
                    )
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        item.quantity = quantity
        item.save(
            update_fields=[
                "quantity",
                "updated_at",
            ]
        )

        serializer = CartItemSerializer(item)

        return Response(serializer.data)

    @action(
        detail=False,
        methods=["delete"],
        url_path=r"items/(?P<item_id>\d+)",
    )
    @transaction.atomic
    def remove_item(self, request, item_id=None):
        cart = self.get_cart(request.user)

        item = get_object_or_404(
            CartItem,
            pk=item_id,
            cart=cart,
        )

        item.delete()

        return Response(
            status=status.HTTP_204_NO_CONTENT
        )

    @action(
        detail=False,
        methods=["post"],
        url_path="coupon",
    )
    @transaction.atomic
    def apply_coupon(self, request):
        code = request.data.get("code")

        if not code:
            return Response(
                {
                    "code": "Le code coupon est obligatoire."
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        coupon = CouponService.find_by_code(code)

        if coupon is None:
            return Response(
                {
                    "code": "Code coupon invalide."
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        cart = self.get_cart(request.user)
        country = self.get_country(request)

        try:
            PricingService.price_cart(
                cart,
                country=country,
                coupon=coupon,
                strict_coupon=True,
            )

        except ValueError as exc:
            return Response(
                {"detail": str(exc)},
                status=status.HTTP_400_BAD_REQUEST,
            )

        cart.coupon = coupon
        cart.save(
            update_fields=[
                "coupon",
                "updated_at",
            ]
        )

        return self.cart_response(request, cart)

    @action(
        detail=False,
        methods=["delete"],
        url_path="coupon",
    )
    @transaction.atomic
    def remove_coupon(self, request):
        cart = self.get_cart(request.user)

        cart.coupon = None
        cart.save(
            update_fields=[
                "coupon",
                "updated_at",
            ]
        )

        return self.cart_response(request, cart)

    @action(
        detail=False,
        methods=["delete"],
        url_path="clear",
    )
    @transaction.atomic
    def clear(self, request):
        cart = self.get_cart(request.user)

        cart.items.all().delete()

        if cart.coupon_id is not None:
            cart.coupon = None
            cart.save(
                update_fields=[
                    "coupon",
                    "updated_at",
                ]
            )

        return Response(
            {
                "message": "Le panier a été vidé."
            },
            status=status.HTTP_200_OK,
        )