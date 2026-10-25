from rest_framework import serializers

from apps.promotions.services import PricingService

from .models import Cart, CartItem


class CartItemSerializer(serializers.ModelSerializer):
    variant_sku = serializers.CharField(
        source="variant.sku",
        read_only=True,
    )

    product_name = serializers.CharField(
        source="variant.product.name",
        read_only=True,
    )

    unit_price = serializers.DecimalField(
        source="variant.price",
        max_digits=12,
        decimal_places=2,
        read_only=True,
    )

    subtotal = serializers.SerializerMethodField()

    class Meta:
        model = CartItem
        fields = [
            "id",
            "variant",
            "variant_sku",
            "product_name",
            "unit_price",
            "quantity",
            "subtotal",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "variant_sku",
            "product_name",
            "unit_price",
            "subtotal",
            "created_at",
            "updated_at",
        ]

    def validate_quantity(self, value):
        if value <= 0:
            raise serializers.ValidationError(
                "La quantité doit être supérieure à 0."
            )

        return value

    def get_subtotal(self, obj):
        return obj.variant.price * obj.quantity


def promotion_data(promotion):
    if promotion is None:
        return None

    return {
        "id": promotion.id,
        "name": promotion.name,
        "discount_type": promotion.discount_type,
        "value": str(promotion.value),
        "ends_at": promotion.ends_at,
    }


class CartSerializer(serializers.ModelSerializer):
    items = serializers.SerializerMethodField()
    total_items = serializers.SerializerMethodField()
    subtotal = serializers.SerializerMethodField()
    promotion_discount = serializers.SerializerMethodField()
    coupon_discount = serializers.SerializerMethodField()
    discount_amount = serializers.SerializerMethodField()
    total_amount = serializers.SerializerMethodField()
    coupon = serializers.SerializerMethodField()
    coupon_error = serializers.SerializerMethodField()

    class Meta:
        model = Cart
        fields = [
            "id",
            "items",
            "total_items",
            "subtotal",
            "promotion_discount",
            "coupon_discount",
            "discount_amount",
            "total_amount",
            "coupon",
            "coupon_error",
            "created_at",
            "updated_at",
        ]
        read_only_fields = fields

    def _pricing(self, obj):
        if not hasattr(self, "_pricing_result"):
            self._pricing_result = PricingService.price_cart(
                obj,
                country=self.context.get("country"),
                coupon=obj.coupon,
            )

        return self._pricing_result

    def get_items(self, obj):
        return [
            {
                "id": item.cart_item.id,
                "variant": item.variant.id,
                "variant_sku": item.variant.sku,
                "product_name": item.variant.product.name,
                "unit_price": str(item.unit_price),
                "quantity": item.quantity,
                "subtotal": str(item.subtotal),
                "discount_amount": str(
                    item.promotion_discount
                ),
                "discounted_unit_price": str(
                    item.discounted_unit_price
                ),
                "discounted_subtotal": str(
                    item.subtotal_after_promotion
                ),
                "promotion": promotion_data(item.promotion),
                "created_at": item.cart_item.created_at,
                "updated_at": item.cart_item.updated_at,
            }
            for item in self._pricing(obj).items
        ]

    def get_total_items(self, obj):
        return sum(
            item.quantity
            for item in obj.items.all()
        )

    def get_subtotal(self, obj):
        return str(self._pricing(obj).subtotal)

    def get_promotion_discount(self, obj):
        return str(self._pricing(obj).promotion_discount)

    def get_coupon_discount(self, obj):
        return str(self._pricing(obj).coupon_discount)

    def get_discount_amount(self, obj):
        return str(self._pricing(obj).discount_amount)

    def get_total_amount(self, obj):
        return str(self._pricing(obj).total_amount)

    def get_coupon(self, obj):
        pricing = self._pricing(obj)
        coupon = pricing.coupon

        if coupon is None:
            return None

        return {
            "id": coupon.id,
            "code": coupon.code,
            "discount_type": coupon.discount_type,
            "value": str(coupon.value),
            "minimum_amount": str(coupon.minimum_amount),
            "discount_amount": str(
                pricing.coupon_discount
            ),
            "ends_at": coupon.ends_at,
        }

    def get_coupon_error(self, obj):
        return self._pricing(obj).coupon_error
