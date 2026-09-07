from rest_framework import serializers

from .models import Category, Brand, Product,ProductCategory


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