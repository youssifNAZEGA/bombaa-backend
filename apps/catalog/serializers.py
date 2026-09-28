from rest_framework import serializers

from .models import (
    Category, 
    Brand, 
    Product,
    ProductCategory,
    ProductImage, 
    Attribute, 
    AttributeValue,
    ProductVariant,
    VariantAttributeValue,
    )


class CategorySerializer(serializers.ModelSerializer):

    children_count = serializers.SerializerMethodField()

    class Meta:
        model = Category

        fields = [
            "id",
            "name",
            "slug",
            "description",
            "parent",
            "is_active",
            "children_count",
            "created_at",
            "updated_at",
        ]

        read_only_fields = [
            "id",
            "children_count",
            "created_at",
            "updated_at",
        ]

    def get_children_count(self, obj):
        return obj.children.count()

    def validate_name(self, value):
        value = value.strip()

        if not value:
            raise serializers.ValidationError(
                "Le nom de la catégorie est obligatoire."
            )

        return value
    
    def validate_parent(self, value):

        if value is None:
            return value

        if self.instance and value.id == self.instance.id:
            raise serializers.ValidationError(
                "Une catégorie ne peut pas être son propre parent."
            )

        return value

class BrandSerializer(serializers.ModelSerializer):

    class Meta:
        model = Brand

        fields = [
            "id",
            "name",
            "description",
            "logo",
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
                "Le nom de la marque est obligatoire."
            )

        return value

class ProductSerializer(serializers.ModelSerializer):

    categories = serializers.PrimaryKeyRelatedField(
        many=True,
        queryset=Category.objects.filter(
            is_active=True
        ),
        required=False,
    )

    class Meta:
        model = Product

        fields = [
            "id",
            "brand",
            "name",
            "slug",
            "description",
            "base_price",
            "categories",
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
                "Le nom du produit est obligatoire."
            )

        return value

    def validate_slug(self, value):

        value = value.strip().lower()

        if not value:
            raise serializers.ValidationError(
                "Le slug du produit est obligatoire."
            )

        return value

    def validate_base_price(self, value):

        if value < 0:
            raise serializers.ValidationError(
                "Le prix du produit ne peut pas être négatif."
            )

        return value

    def create(self, validated_data):

        categories = validated_data.pop(
            "categories",
            []
        )

        product = Product.objects.create(
            **validated_data
        )

        ProductCategory.objects.bulk_create([
            ProductCategory(
                product=product,
                category=category
            )
            for category in categories
        ])

        return product

    def update(self, instance, validated_data):

        categories = validated_data.pop(
            "categories",
            None
        )

        instance = super().update(
            instance,
            validated_data
        )

        if categories is not None:

            ProductCategory.objects.filter(
                product=instance
            ).delete()

            ProductCategory.objects.bulk_create([
                ProductCategory(
                    product=instance,
                    category=category
                )
                for category in categories
            ])

        return instance


class ProductImageSerializer(serializers.ModelSerializer):

    class Meta:
        model = ProductImage

        fields = [
            "id",
            "product",
            "image_url",
            "alt_text",
            "is_primary",
            "created_at",
        ]

        read_only_fields = [
            "id",
            "created_at",
        ]

    def validate_image_url(self, value):

        value = value.strip()

        if not value:
            raise serializers.ValidationError(
                "L'URL de l'image est obligatoire."
            )

        return value

    def validate_alt_text(self, value):

        if value is None:
            return value

        value = value.strip()

        return value or None

class AttributeSerializer(serializers.ModelSerializer):

    values_count = serializers.SerializerMethodField()

    class Meta:
        model = Attribute

        fields = [
            "id",
            "name",
            "values_count",
        ]

        read_only_fields = [
            "id",
            "values_count",
        ]

    def get_values_count(self, obj):
        return obj.values.count()

    def validate_name(self, value):

        value = value.strip()

        if not value:
            raise serializers.ValidationError(
                "Le nom de l'attribut est obligatoire."
            )

        return value


class AttributeValueSerializer(serializers.ModelSerializer):

    class Meta:
        model = AttributeValue

        fields = [
            "id",
            "attribute",
            "value",
        ]

        read_only_fields = [
            "id",
        ]

    def validate_value(self, value):

        value = value.strip()

        if not value:
            raise serializers.ValidationError(
                "La valeur de l'attribut est obligatoire."
            )

        return value

class AttributeValueSerializer(serializers.ModelSerializer):

    class Meta:
        model = AttributeValue

        fields = [
            "id",
            "attribute",
            "value",
        ]

        read_only_fields = [
            "id",
        ]

    def validate_value(self, value):

        value = value.strip()

        if not value:
            raise serializers.ValidationError(
                "La valeur de l'attribut est obligatoire."
            )

        return value

class ProductVariantSerializer(serializers.ModelSerializer):

    class Meta:
        model = ProductVariant

        fields = [
            "id",
            "product",
            "sku",
            "price",
            "is_active",
            "created_at",
            "updated_at",
        ]

        read_only_fields = [
            "id",
            "created_at",
            "updated_at",
        ]

    def validate_sku(self, value):

        value = value.strip().upper()

        if not value:
            raise serializers.ValidationError(
                "Le SKU est obligatoire."
            )

        return value

    def validate_price(self, value):

        if value < 0:
            raise serializers.ValidationError(
                "Le prix ne peut pas être négatif."
            )

        return value

class VariantAttributeValueSerializer(serializers.ModelSerializer):

    class Meta:
        model = VariantAttributeValue

        fields = [
            "variant",
            "attribute_value",
        ]

    def validate(self, attrs):

        variant = attrs["variant"]
        attribute_value = attrs["attribute_value"]

        attribute_id = attribute_value.attribute_id

        exists = (
            VariantAttributeValue.objects
            .filter(
                variant=variant,
                attribute_value__attribute_id=attribute_id,
            )
            .exclude(
                attribute_value=attribute_value,
            )
            .exists()
        )

        if exists:
            raise serializers.ValidationError(
                {
                    "attribute_value": (
                        "Cette variante possède déjà "
                        "une valeur pour cet attribut."
                    )
                }
            )

        return attrs

