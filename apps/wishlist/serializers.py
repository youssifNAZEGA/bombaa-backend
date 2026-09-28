from rest_framework import serializers

from .models import Wishlist, WishlistItem


class WishlistItemSerializer(serializers.ModelSerializer):
    variant_sku = serializers.CharField(
        source="variant.sku",
        read_only=True,
    )

    product_name = serializers.CharField(
        source="variant.product.name",
        read_only=True,
    )

    price = serializers.DecimalField(
        source="variant.price",
        max_digits=12,
        decimal_places=2,
        read_only=True,
    )

    class Meta:
        model = WishlistItem
        fields = [
            "id",
            "variant",
            "variant_sku",
            "product_name",
            "price",
            "created_at",
        ]
        read_only_fields = [
            "id",
            "variant_sku",
            "product_name",
            "price",
            "created_at",
        ]


class WishlistSerializer(serializers.ModelSerializer):
    items = WishlistItemSerializer(
        many=True,
        read_only=True,
    )

    class Meta:
        model = Wishlist
        fields = [
            "id",
            "items",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "items",
            "created_at",
            "updated_at",
        ]