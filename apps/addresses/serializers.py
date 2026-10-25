from django.db.models import Q

from rest_framework import serializers

from apps.geography.models import Country
from apps.geography.serializers import CountrySummarySerializer

from .models import Address


class AddressSerializer(serializers.ModelSerializer):

    country = serializers.CharField(
        max_length=100,
        required=False,
        allow_blank=True,
    )

    country_id = serializers.PrimaryKeyRelatedField(
        source="country_ref",
        queryset=Country.objects.filter(is_active=True),
        required=False,
        allow_null=True,
    )

    country_detail = serializers.SerializerMethodField()

    country_code = serializers.SerializerMethodField()

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
            "country_id",
            "country_code",
            "country_detail",
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

    def validate(self, attrs):
        country_ref = attrs.get("country_ref")
        country_name = attrs.get("country")

        if country_ref is not None:
            attrs["country"] = country_ref.name

        elif country_name:
            country_name = country_name.strip()

            resolved_country = (
                Country.objects
                .filter(is_active=True)
                .filter(
                    Q(name__iexact=country_name)
                    | Q(code__iexact=country_name)
                )
                .first()
            )

            if resolved_country is not None:
                attrs["country_ref"] = resolved_country
                attrs["country"] = resolved_country.name

        if (
            self.instance is None
            and not attrs.get("country")
            and not attrs.get("country_ref")
        ):
            raise serializers.ValidationError({
                "country": "Le pays est obligatoire."
            })

        return attrs

    def get_country_detail(self, obj):
        if obj.country_ref_id is None:
            return None

        return CountrySummarySerializer(obj.country_ref).data

    def get_country_code(self, obj):
        if obj.country_ref_id is None:
            return None

        return obj.country_ref.code