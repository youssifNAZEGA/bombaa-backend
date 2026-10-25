from decimal import Decimal

from rest_framework import serializers

from apps.payments.models import PaymentMethod

from .models import Country, Currency


class CurrencySerializer(serializers.ModelSerializer):

    class Meta:
        model = Currency

        fields = [
            "id",
            "code",
            "name",
            "symbol",
            "exchange_rate",
            "is_base",
            "is_active",
            "created_at",
            "updated_at",
        ]

        read_only_fields = [
            "id",
            "created_at",
            "updated_at",
        ]

    def validate_code(self, value):
        value = value.strip().upper()

        if len(value) != 3:
            raise serializers.ValidationError(
                "Le code de la devise doit contenir 3 caractères."
            )

        return value

    def validate_name(self, value):
        value = value.strip()

        if not value:
            raise serializers.ValidationError(
                "Le nom de la devise est obligatoire."
            )

        return value

    def validate_symbol(self, value):
        value = value.strip()

        if not value:
            raise serializers.ValidationError(
                "Le symbole de la devise est obligatoire."
            )

        return value

    def validate_exchange_rate(self, value):
        if value <= 0:
            raise serializers.ValidationError(
                "Le taux de change doit être supérieur à 0."
            )

        return value

    def validate(self, attrs):
        is_base = attrs.get(
            "is_base",
            getattr(self.instance, "is_base", False),
        )

        exchange_rate = attrs.get(
            "exchange_rate",
            getattr(
                self.instance,
                "exchange_rate",
                Decimal("1.000000"),
            ),
        )

        if is_base and exchange_rate != Decimal("1.000000"):
            raise serializers.ValidationError({
                "exchange_rate": (
                    "La devise principale doit avoir un taux de 1."
                )
            })

        return attrs


class CurrencySummarySerializer(serializers.ModelSerializer):

    class Meta:
        model = Currency
        fields = [
            "id",
            "code",
            "name",
            "symbol",
        ]


class PaymentMethodSummarySerializer(serializers.ModelSerializer):

    class Meta:
        model = PaymentMethod
        fields = [
            "id",
            "name",
            "code",
        ]


class CountrySerializer(serializers.ModelSerializer):

    currency_detail = CurrencySummarySerializer(
        source="currency",
        read_only=True,
    )

    payment_methods = serializers.PrimaryKeyRelatedField(
        many=True,
        queryset=PaymentMethod.objects.all(),
        required=False,
    )

    payment_methods_detail = PaymentMethodSummarySerializer(
        source="payment_methods",
        many=True,
        read_only=True,
    )

    class Meta:
        model = Country

        fields = [
            "id",
            "name",
            "code",
            "phone_code",
            "currency",
            "currency_detail",
            "payment_methods",
            "payment_methods_detail",
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
                "Le nom du pays est obligatoire."
            )

        return value

    def validate_code(self, value):
        value = value.strip().upper()

        if len(value) != 2:
            raise serializers.ValidationError(
                "Le code du pays doit contenir 2 caractères."
            )

        return value

    def validate_phone_code(self, value):
        if value is None:
            return value

        value = value.strip()

        return value or None


class CountrySummarySerializer(serializers.ModelSerializer):

    currency_code = serializers.CharField(
        source="currency.code",
        read_only=True,
    )

    class Meta:
        model = Country
        fields = [
            "id",
            "name",
            "code",
            "currency_code",
        ]
