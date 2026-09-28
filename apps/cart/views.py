from django.db import transaction
from django.shortcuts import get_object_or_404

from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.catalog.models import ProductVariant

from .models import Cart, CartItem
from .serializers import CartItemSerializer, CartSerializer


class CartViewSet(viewsets.ViewSet):
    permission_classes = [IsAuthenticated]

    def get_cart(self, user):
        cart, _ = Cart.objects.get_or_create(
            user=user
        )
        return cart

    def list(self, request):
        cart = self.get_cart(request.user)

        cart = (
            Cart.objects
            .prefetch_related(
                "items__variant__product"
            )
            .get(pk=cart.pk)
        )

        serializer = CartSerializer(cart)

        return Response(serializer.data)

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
        methods=["delete"],
        url_path="clear",
    )
    @transaction.atomic
    def clear(self, request):
        cart = self.get_cart(request.user)

        cart.items.all().delete()

        return Response(
            {
                "message": "Le panier a été vidé."
            },
            status=status.HTTP_200_OK,
        )