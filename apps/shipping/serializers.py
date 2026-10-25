from django.utils import timezone

from rest_framework import serializers

from apps.geography.models import Country
from apps.geography.serializers import CountrySummarySerializer

from .models import (
    Delivery,
    ShippingMethod,
    ShippingRate,
    ShippingZone,
)
from .services import ShippingService


class ShippingZoneSerializer(serializers.ModelSerializer):

    countries = serializers.PrimaryKeyRelatedField(
        many=True,
        queryset=Country.objects.filter(is_active=True),
        required=False,
    )

    countries_detail = CountrySummarySerializer(
        source="countries",
        many=True,
        read_only=True,
    )

    class Meta:
        model = ShippingZone

        fields = [
            "id",
            "name",
            "description",
            "countries",
            "countries_detail",
            "is_active",
            "created_at",
            "updated_at",
        ]

        read_only_fields = [
            "id",
            "created_at",
            "updated_at",
        ]

    def validate_name(self, value):
        value = value.strip()

        if not value:
            raise serializers.ValidationError(
                "Le nom de la zone de livraison est obligatoire."
            )

        return value


class ShippingMethodSerializer(serializers.ModelSerializer):

    class Meta:
        model = ShippingMethod

        fields = [
            "id",
            "name",
            "code",
            "description",
            "carrier",
            "estimated_days",
            "is_active",
            "created_at",
            "updated_at",
        ]

        read_only_fields = [
            "id",
            "created_at",
            "updated_at",
        ]

    def validate_name(self, value):
        value = value.strip()

        if not value:
            raise serializers.ValidationError(
                "Le nom du mode de livraison est obligatoire."
            )

        return value

    def validate_code(self, value):
        value = value.strip().upper()

        if not value:
            raise serializers.ValidationError(
                "Le code du mode de livraison est obligatoire."
            )

        return value

    def validate_carrier(self, value):
        if value is None:
            return value

        value = value.strip()

        return value or None

    def validate_estimated_days(self, value):
        if value < 0:
            raise serializers.ValidationError(
                "Le délai estimé ne peut pas être négatif."
            )

        return value


class ShippingRateSerializer(serializers.ModelSerializer):

    zone_name = serializers.CharField(
        source="zone.name",
        read_only=True,
    )

    method_name = serializers.CharField(
        source="method.name",
        read_only=True,
    )

    currency_code = serializers.CharField(
        source="currency.code",
        read_only=True,
        allow_null=True,
    )

    class Meta:
        model = ShippingRate

        fields = [
            "id",
            "zone",
            "zone_name",
            "method",
            "method_name",
            "min_weight_grams",
            "max_weight_grams",
            "price",
            "currency",
            "currency_code",
            "is_active",
            "created_at",
            "updated_at",
        ]

        read_only_fields = [
            "id",
            "created_at",
            "updated_at",
        ]

    def validate(self, attrs):
        min_weight = attrs.get(
            "min_weight_grams",
            getattr(self.instance, "min_weight_grams", 0),
        )

        max_weight = attrs.get(
            "max_weight_grams",
            getattr(self.instance, "max_weight_grams", None),
        )

        if max_weight is not None and max_weight < min_weight:
            raise serializers.ValidationError({
                "max_weight_grams": (
                    "Le poids maximum doit être supérieur ou égal "
                    "au poids minimum."
                )
            })

        price = attrs.get(
            "price",
            getattr(self.instance, "price", None),
        )

        if price is not None and price < 0:
            raise serializers.ValidationError({
                "price": "Le prix ne peut pas être négatif."
            })

        return attrs


class DeliverySerializer(serializers.ModelSerializer):

    order_reference = serializers.CharField(
        source="order.reference",
        read_only=True,
    )

    shipping_method_detail = ShippingMethodSerializer(
        source="shipping_method",
        read_only=True,
    )

    class Meta:
        model = Delivery

        fields = [
            "id",
            "order",
            "order_reference",
            "shipping_method",
            "shipping_method_detail",
            "tracking_number",
            "status",
            "shipped_at",
            "delivered_at",
            "estimated_delivery_date",
            "created_at",
            "updated_at",
        ]

        read_only_fields = [
            "id",
            "order_reference",
            "created_at",
            "updated_at",
        ]

    def validate_tracking_number(self, value):
        if value is None:
            return value

        value = value.strip()

        return value or None

    def create(self, validated_data):
        method = validated_data.get("shipping_method")

        if (
            method is not None
            and not validated_data.get("estimated_delivery_date")
        ):
            validated_data["estimated_delivery_date"] = (
                ShippingService.estimated_delivery_date(method)
            )

        return super().create(validated_data)

    def update(self, instance, validated_data):
        instance = super().update(instance, validated_data)

        now = timezone.now()
        update_fields = []

        if (
            instance.status == Delivery.Status.SHIPPED
            and instance.shipped_at is None
        ):
            instance.shipped_at = now
            update_fields.append("shipped_at")

        if instance.status == Delivery.Status.DELIVERED:
            if instance.shipped_at is None:
                instance.shipped_at = now
                update_fields.append("shipped_at")

            if instance.delivered_at is None:
                instance.delivered_at = now
                update_fields.append("delivered_at")

        if update_fields:
            update_fields.append("updated_at")
            instance.save(update_fields=update_fields)

        return instance
