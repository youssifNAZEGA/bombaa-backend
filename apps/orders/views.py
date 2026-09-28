from decimal import Decimal
from uuid import uuid4

from django.db import transaction
from django.shortcuts import get_object_or_404

from rest_framework import status, viewsets
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.cart.models import Cart
from apps.stocks.models import Stock

from .models import Order, OrderAddress, OrderItem
from .serializers import OrderSerializer


class OrderViewSet(viewsets.ViewSet):
    permission_classes = [IsAuthenticated]

    def list(self, request):
        orders = (
            Order.objects
            .filter(user=request.user)
            .prefetch_related("items")
            .select_related("shipping_address")
        )

        serializer = OrderSerializer(
            orders,
            many=True,
        )

        return Response(serializer.data)

    def retrieve(self, request, pk=None):
        order = get_object_or_404(
            Order.objects
            .prefetch_related("items")
            .select_related("shipping_address"),
            pk=pk,
            user=request.user,
        )

        serializer = OrderSerializer(order)

        return Response(serializer.data)

    @transaction.atomic
    def create(self, request):
        user = request.user

        cart = (
            Cart.objects
            .prefetch_related(
                "items__variant__product"
            )
            .filter(user=user)
            .first()
        )

        if not cart:
            return Response(
                {
                    "detail": "Votre panier est vide."
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        cart_items = list(cart.items.all())

        if not cart_items:
            return Response(
                {
                    "detail": "Votre panier est vide."
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        address_id = request.data.get(
            "address_id"
        )

        if not address_id:
            return Response(
                {
                    "address_id": (
                        "L'adresse de livraison est obligatoire."
                    )
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        from apps.addresses.models import Address

        address = get_object_or_404(
            Address,
            pk=address_id,
            user=user,
        )

        subtotal = Decimal("0.00")

        checked_items = []

        for cart_item in cart_items:
            variant = cart_item.variant

            if not variant.is_active:
                return Response(
                    {
                        "detail": (
                            f"La variante "
                            f"{variant.sku} n'est plus disponible."
                        )
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )

            try:
                stock = (
                    Stock.objects
                    .select_for_update()
                    .get(variant=variant)
                )
            except Stock.DoesNotExist:
                return Response(
                    {
                        "detail": (
                            f"Aucun stock n'est configuré "
                            f"pour {variant.sku}."
                        )
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )

            available_quantity = (
                stock.quantity
                - stock.reserved_quantity
            )

            if cart_item.quantity > available_quantity:
                return Response(
                    {
                        "detail": (
                            f"Stock insuffisant pour "
                            f"{variant.sku}. "
                            f"Disponible : "
                            f"{available_quantity}."
                        )
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )

            item_subtotal = (
                variant.price * cart_item.quantity
            )

            subtotal += item_subtotal

            checked_items.append(
                {
                    "cart_item": cart_item,
                    "variant": variant,
                    "stock": stock,
                    "subtotal": item_subtotal,
                }
            )

        shipping_cost = Decimal(
            str(request.data.get(
                "shipping_cost",
                "0.00",
            ))
        )

        if shipping_cost < 0:
            return Response(
                {
                    "shipping_cost": (
                        "Le coût de livraison "
                        "ne peut pas être négatif."
                    )
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        discount_amount = Decimal(
            str(request.data.get(
                "discount_amount",
                "0.00",
            ))
        )

        if discount_amount < 0:
            return Response(
                {
                    "discount_amount": (
                        "La remise ne peut pas être négative."
                    )
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        if discount_amount > subtotal:
            return Response(
                {
                    "discount_amount": (
                        "La remise ne peut pas dépasser "
                        "le sous-total."
                    )
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        total_amount = (
            subtotal
            + shipping_cost
            - discount_amount
        )

        reference = (
            f"CMD-{uuid4().hex[:12].upper()}"
        )

        order = Order.objects.create(
            user=user,
            reference=reference,
            status=Order.Status.PENDING,
            subtotal=subtotal,
            shipping_cost=shipping_cost,
            discount_amount=discount_amount,
            total_amount=total_amount,
            currency="XOF",
            notes=request.data.get("notes"),
        )

        OrderAddress.objects.create(
            order=order,
            recipient_name=(
                f"{address.first_name} "
                f"{address.last_name}"
            ),
            phone=address.phone,
            address_line1=address.address_line_1,
            address_line2=address.address_line_2,
            city=address.city,
            state=address.state,
            postal_code=address.postal_code,
            country_name=address.country,
            country_code="",
        )

        for item_data in checked_items:
            cart_item = item_data["cart_item"]
            variant = item_data["variant"]
            stock = item_data["stock"]

            OrderItem.objects.create(
                order=order,
                variant=variant,
                product_name=variant.product.name,
                variant_description=variant.sku,
                sku=variant.sku,
                quantity=cart_item.quantity,
                unit_price=variant.price,
                subtotal=item_data["subtotal"],
            )

            stock.reserved_quantity += (
                cart_item.quantity
            )

            stock.save(
                update_fields=[
                    "reserved_quantity",
                    "updated_at",
                ]
            )

        cart.items.all().delete()

        serializer = OrderSerializer(order)

        return Response(
            serializer.data,
            status=status.HTTP_201_CREATED,
        )