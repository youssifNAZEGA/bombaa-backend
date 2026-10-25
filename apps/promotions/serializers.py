from rest_framework import serializers

from apps.catalog.models import (
    Brand,
    Category,
    Product,
)
from apps.geography.models import Country

from .models import Coupon, DiscountType, Promotion
from .services import CouponService


class PromotionProductSummarySerializer(serializers.ModelSerializer):
    class Meta:
        model = Product
        fields = ["id", "name", "slug"]


class PromotionCategorySummarySerializer(serializers.ModelSerializer):
    class Meta:
        model = Category
        fields = ["id", "name", "slug"]


class PromotionBrandSummarySerializer(serializers.ModelSerializer):
    class Meta:
        model = Brand
        fields = ["id", "name"]


class PromotionCountrySummarySerializer(serializers.ModelSerializer):
    class Meta:
        model = Country
        fields = ["id", "name", "code"]


def _validate_discount(serializer, attrs):
    instance = serializer.instance
    discount_type = attrs.get(
        "discount_type",
        instance.discount_type if instance else None,
    )
    value = attrs.get(
        "value",
        instance.value if instance else None,
    )

    if value is not None:
        if value <= 0:
            raise serializers.ValidationError(
                {
                    "value": (
                        "La valeur de la remise doit être "
                        "supérieure à 0."
                    )
                }
            )

        if (
            discount_type == DiscountType.PERCENTAGE
            and value > 100
        ):
            raise serializers.ValidationError(
                {
                    "value": (
                        "Un pourcentage de réduction ne peut "
                        "pas dépasser 100."
                    )
                }
            )

    starts_at = attrs.get(
        "starts_at",
        instance.starts_at if instance else None,
    )
    ends_at = attrs.get(
        "ends_at",
        instance.ends_at if instance else None,
    )

    if starts_at and ends_at and starts_at > ends_at:
        raise serializers.ValidationError(
            {
                "ends_at": (
                    "La date de fin doit être postérieure "
                    "à la date de début."
                )
            }
        )


class PromotionSerializer(serializers.ModelSerializer):
    products = serializers.PrimaryKeyRelatedField(
        many=True,
        queryset=Product.objects.all(),
        required=False,
    )

    categories = serializers.PrimaryKeyRelatedField(
        many=True,
        queryset=Category.objects.all(),
        required=False,
    )

    brands = serializers.PrimaryKeyRelatedField(
        many=True,
        queryset=Brand.objects.all(),
        required=False,
    )

    countries = serializers.PrimaryKeyRelatedField(
        many=True,
        queryset=Country.objects.all(),
        required=False,
    )

    products_detail = PromotionProductSummarySerializer(
        source="products",
        many=True,
        read_only=True,
    )

    categories_detail = PromotionCategorySummarySerializer(
        source="categories",
        many=True,
        read_only=True,
    )

    brands_detail = PromotionBrandSummarySerializer(
        source="brands",
        many=True,
        read_only=True,
    )

    countries_detail = PromotionCountrySummarySerializer(
        source="countries",
        many=True,
        read_only=True,
    )

    is_running = serializers.SerializerMethodField()
    discount_label = serializers.SerializerMethodField()

    class Meta:
        model = Promotion
        fields = [
            "id",
            "name",
            "description",
            "discount_type",
            "value",
            "starts_at",
            "ends_at",
            "is_active",
            "is_running",
            "discount_label",
            "products",
            "categories",
            "brands",
            "countries",
            "products_detail",
            "categories_detail",
            "brands_detail",
            "countries_detail",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "is_running",
            "discount_label",
            "products_detail",
            "categories_detail",
            "brands_detail",
            "countries_detail",
            "created_at",
            "updated_at",
        ]

    def validate(self, attrs):
        _validate_discount(self, attrs)
        return attrs

    def get_is_running(self, obj):
        return obj.is_running()

    def get_discount_label(self, obj):
        if obj.discount_type == DiscountType.PERCENTAGE:
            return f"-{obj.value}%"

        return f"-{obj.value}"


class CouponSerializer(serializers.ModelSerializer):
    code = serializers.CharField(
        max_length=50,
        required=False,
        allow_blank=True,
    )

    products = serializers.PrimaryKeyRelatedField(
        many=True,
        queryset=Product.objects.all(),
        required=False,
    )

    categories = serializers.PrimaryKeyRelatedField(
        many=True,
        queryset=Category.objects.all(),
        required=False,
    )

    countries = serializers.PrimaryKeyRelatedField(
        many=True,
        queryset=Country.objects.all(),
        required=False,
    )

    products_detail = PromotionProductSummarySerializer(
        source="products",
        many=True,
        read_only=True,
    )

    categories_detail = PromotionCategorySummarySerializer(
        source="categories",
        many=True,
        read_only=True,
    )

    countries_detail = PromotionCountrySummarySerializer(
        source="countries",
        many=True,
        read_only=True,
    )

    current_uses = serializers.SerializerMethodField()
    remaining_uses = serializers.SerializerMethodField()
    is_running = serializers.SerializerMethodField()
    discount_label = serializers.SerializerMethodField()

    class Meta:
        model = Coupon
        fields = [
            "id",
            "code",
            "description",
            "discount_type",
            "value",
            "starts_at",
            "ends_at",
            "minimum_amount",
            "max_uses",
            "current_uses",
            "remaining_uses",
            "is_active",
            "is_running",
            "discount_label",
            "products",
            "categories",
            "countries",
            "products_detail",
            "categories_detail",
            "countries_detail",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "current_uses",
            "remaining_uses",
            "is_running",
            "discount_label",
            "products_detail",
            "categories_detail",
            "countries_detail",
            "created_at",
            "updated_at",
        ]

    def validate_code(self, value):
        value = str(value or "").strip().upper()

        if not value:
            if self.instance is not None:
                return self.instance.code

            return ""

        queryset = Coupon.objects.filter(code__iexact=value)

        if self.instance is not None:
            queryset = queryset.exclude(
                pk=self.instance.pk
            )

        if queryset.exists():
            raise serializers.ValidationError(
                "Un coupon avec ce code existe déjà."
            )

        return value

    def validate_max_uses(self, value):
        if value is not None and value < 1:
            raise serializers.ValidationError(
                "Le nombre maximum d'utilisations doit "
                "être supérieur à 0."
            )

        return value

    def validate(self, attrs):
        _validate_discount(self, attrs)
        return attrs

    def create(self, validated_data):
        products = validated_data.pop("products", [])
        categories = validated_data.pop("categories", [])
        countries = validated_data.pop("countries", [])
        code = validated_data.pop("code", "")
        code = code or CouponService.generate_code()

        coupon = Coupon.objects.create(
            code=code,
            **validated_data,
        )

        coupon.products.set(products)
        coupon.categories.set(categories)
        coupon.countries.set(countries)

        return coupon

    def update(self, instance, validated_data):
        code = validated_data.pop("code", None)

        if code:
            instance.code = code

        return super().update(instance, validated_data)

    def get_current_uses(self, obj):
        return obj.current_uses

    def get_remaining_uses(self, obj):
        return obj.remaining_uses

    def get_is_running(self, obj):
        return obj.is_running()

    def get_discount_label(self, obj):
        if obj.discount_type == DiscountType.PERCENTAGE:
            return f"-{obj.value}%"

        return f"-{obj.value}"
