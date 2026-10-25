from django.core.exceptions import ObjectDoesNotExist

from rest_framework import serializers

from apps.shipping.serializers import DeliverySerializer

from .models import Order, OrderAddress, OrderItem


class OrderItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = OrderItem
        fields = [
            "id",
            "variant",
            "product_name",
            "variant_description",
            "sku",
            "quantity",
            "unit_price",
            "subtotal",
            "discount_amount",
        ]
        read_only_fields = fields


class OrderAddressSerializer(serializers.ModelSerializer):
    class Meta:
        model = OrderAddress
        fields = [
            "id",
            "recipient_name",
            "phone",
            "address_line1",
            "address_line2",
            "city",
            "state",
            "postal_code",
            "country_name",
            "country_code",
        ]
        read_only_fields = ["id"]


class OrderSerializer(serializers.ModelSerializer):
    items = OrderItemSerializer(
        many=True,
        read_only=True,
    )

    shipping_address = OrderAddressSerializer(
        read_only=True,
    )

    delivery = serializers.SerializerMethodField()

    class Meta:
        model = Order
        fields = [
            "id",
            "reference",
            "status",
            "subtotal",
            "shipping_cost",
            "shipping_weight_grams",
            "promotion_discount",
            "coupon_discount",
            "coupon_code",
            "discount_details",
            "discount_amount",
            "total_amount",
            "currency",
            "notes",
            "shipping_address",
            "delivery",
            "items",
            "created_at",
            "updated_at",
        ]
        read_only_fields = fields

    def get_delivery(self, obj):
        try:
            delivery = obj.delivery
        except ObjectDoesNotExist:
            return None

        return DeliverySerializer(delivery).data

        