from rest_framework import serializers

from .models import Address


class AddressSerializer(serializers.ModelSerializer):

    class Meta:
        model = Address

        fields = [
            "id",
            "label",
            "first_name",
            "last_name",
            "phone",
            "address_line_1",
            "address_line_2",
            "city",
            "state",
            "postal_code",
            "country",
            "is_default",
            "created_at",
            "updated_at",
        ]

        read_only_fields = [
            "id",
            "created_at",
            "updated_at",
        ]

    def validate_phone(self, value):
        value = value.strip()

        if not value:
            raise serializers.ValidationError(
                "Le numéro de téléphone est obligatoire."
            )

        return value

    def validate_country(self, value):
        value = value.strip()

        if not value:
            raise serializers.ValidationError(
                "Le pays est obligatoire."
            )

        return value