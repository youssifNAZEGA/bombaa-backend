from rest_framework import serializers

from .models import Stock, StockMovement


class StockSerializer(serializers.ModelSerializer):

    available_quantity = serializers.SerializerMethodField()

    class Meta:
        model = Stock

        fields = [
            "id",
            "variant",
            "quantity",
            "reserved_quantity",
            "minimum_quantity",
            "available_quantity",
            "updated_at",
        ]

        read_only_fields = [
            "id",
            "available_quantity",
            "updated_at",
        ]

    def get_available_quantity(self, obj):
        return obj.quantity - obj.reserved_quantity

    def validate(self, attrs):

        quantity = attrs.get(
            "quantity",
            self.instance.quantity if self.instance else 0
        )

        reserved_quantity = attrs.get(
            "reserved_quantity",
            self.instance.reserved_quantity
            if self.instance
            else 0
        )

        minimum_quantity = attrs.get(
            "minimum_quantity",
            self.instance.minimum_quantity
            if self.instance
            else 0
        )

        if quantity < 0:
            raise serializers.ValidationError({
                "quantity": (
                    "La quantité ne peut pas être négative."
                )
            })

        if reserved_quantity < 0:
            raise serializers.ValidationError({
                "reserved_quantity": (
                    "La quantité réservée ne peut pas être négative."
                )
            })

        if minimum_quantity < 0:
            raise serializers.ValidationError({
                "minimum_quantity": (
                    "La quantité minimale ne peut pas être négative."
                )
            })

        if reserved_quantity > quantity:
            raise serializers.ValidationError({
                "reserved_quantity": (
                    "La quantité réservée ne peut pas "
                    "être supérieure à la quantité disponible."
                )
            })

        return attrs



class StockMovementSerializer(serializers.ModelSerializer):
    class Meta:
        model = StockMovement
        fields = [
            "id",
            "stock",
            "movement_type",
            "quantity",
            "reason",
            "created_at",
        ]
        read_only_fields = [
            "id",
            "created_at",
        ]

    def validate_quantity(self, value):
        if value <= 0:
            raise serializers.ValidationError(
                "La quantité doit être supérieure à 0."
            )

        return value