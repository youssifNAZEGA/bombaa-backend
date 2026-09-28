from rest_framework import serializers

from .models import PaymentMethod, Payment, Transaction


class PaymentMethodSerializer(serializers.ModelSerializer):
    class Meta:
        model = PaymentMethod
        fields = [
            "id",
            "name",
            "code",
            "description",
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
                "Le nom du moyen de paiement est obligatoire."
            )

        return value

    def validate_code(self, value):
        value = value.strip().upper()

        if not value:
            raise serializers.ValidationError(
                "Le code du moyen de paiement est obligatoire."
            )

        return value


class PaymentSerializer(serializers.ModelSerializer):
    order_reference = serializers.CharField(
        source="order.reference",
        read_only=True,
    )

    payment_method_name = serializers.CharField(
        source="payment_method.name",
        read_only=True,
    )

    class Meta:
        model = Payment
        fields = [
            "id",
            "order",
            "order_reference",
            "payment_method",
            "payment_method_name",
            "reference",
            "amount",
            "currency",
            "status",
            "paid_at",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "reference",
            "status",
            "paid_at",
            "created_at",
            "updated_at",
        ]

    def validate_amount(self, value):
        if value <= 0:
            raise serializers.ValidationError(
                "Le montant du paiement doit être supérieur à 0."
            )

        return value

    def validate_currency(self, value):
        value = value.strip().upper()

        if len(value) != 3:
            raise serializers.ValidationError(
                "La devise doit contenir exactement 3 caractères."
            )

        return value


class TransactionSerializer(serializers.ModelSerializer):
    payment_reference = serializers.CharField(
        source="payment.reference",
        read_only=True,
    )

    class Meta:
        model = Transaction
        fields = [
            "id",
            "payment",
            "payment_reference",
            "reference",
            "external_reference",
            "amount",
            "currency",
            "status",
            "transaction_date",
            "response_message",
            "created_at",
        ]
        read_only_fields = [
            "id",
            "reference",
            "status",
            "transaction_date",
            "created_at",
        ]

    def validate_amount(self, value):
        if value <= 0:
            raise serializers.ValidationError(
                "Le montant de la transaction doit être supérieur à 0."
            )

        return value

    def validate_currency(self, value):
        value = value.strip().upper()

        if len(value) != 3:
            raise serializers.ValidationError(
                "La devise doit contenir exactement 3 caractères."
            )

        return value