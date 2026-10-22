from uuid import uuid4

from django.core.exceptions import ObjectDoesNotExist
from django.utils.text import slugify

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

    slug = serializers.SlugField(
        max_length=255,
        required=False,
        allow_blank=True,
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

        return value.strip().lower()

    def validate(self, attrs):

        slug = attrs.get("slug", "").strip().lower()

        if not slug:
            if self.instance:
                slug = self.instance.slug
            else:
                slug = slugify(attrs.get("name", ""))

                if not slug:
                    slug = f"produit-{uuid4().hex[:8]}"

        existing = Product.objects.filter(slug=slug)

        if self.instance:
            existing = existing.exclude(pk=self.instance.pk)

        if existing.exists():
            raise serializers.ValidationError({
                "slug": (
                    "Un produit avec ce slug existe déjà."
                )
            })

        attrs["slug"] = slug

        return attrs

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



class BrandSummarySerializer(serializers.ModelSerializer):

    class Meta:
        model = Brand
        fields = [
            "id",
            "name",
        ]


class ProductImageReadSerializer(serializers.ModelSerializer):

    class Meta:
        model = ProductImage
        fields = [
            "id",
            "image_url",
            "alt_text",
            "is_primary",
        ]


class VariantAttributeValueReadSerializer(
    serializers.ModelSerializer
):

    attribute_value_id = serializers.IntegerField(
        source="attribute_value.id",
        read_only=True,
    )

    attribute_id = serializers.IntegerField(
        source="attribute_value.attribute.id",
        read_only=True,
    )

    attribute = serializers.CharField(
        source="attribute_value.attribute.name",
        read_only=True,
    )

    value = serializers.CharField(
        source="attribute_value.value",
        read_only=True,
    )

    class Meta:
        model = VariantAttributeValue
        fields = [
            "attribute_value_id",
            "attribute_id",
            "attribute",
            "value",
        ]


class ProductVariantReadSerializer(
    serializers.ModelSerializer
):

    attributes = VariantAttributeValueReadSerializer(
        source="variant_attribute_values",
        many=True,
        read_only=True,
    )

    stock = serializers.SerializerMethodField()

    class Meta:
        model = ProductVariant
        fields = [
            "id",
            "sku",
            "price",
            "is_active",
            "attributes",
            "stock",
        ]

    def get_stock(self, obj):

        try:
            stock = obj.stock
        except ObjectDoesNotExist:
            return None

        available_quantity = max(
            stock.quantity - stock.reserved_quantity,
            0,
        )

        return {
            "quantity": stock.quantity,
            "reserved_quantity": stock.reserved_quantity,
            "available_quantity": available_quantity,
            "in_stock": available_quantity > 0,
        }


def product_is_in_stock(product):

    for variant in product.variants.all():

        if not variant.is_active:
            continue

        try:
            stock = variant.stock
        except ObjectDoesNotExist:
            continue

        if stock.quantity - stock.reserved_quantity > 0:
            return True

    return False


def product_categories_data(product):

    return [
        {
            "id": product_category.category.id,
            "name": product_category.category.name,
            "slug": product_category.category.slug,
        }
        for product_category in product.product_categories.all()
    ]


def product_primary_image_data(product):

    images = list(product.images.all())

    if not images:
        return None

    primary_image = next(
        (
            image
            for image in images
            if image.is_primary
        ),
        images[0],
    )

    return ProductImageReadSerializer(primary_image).data


class ProductListSerializer(serializers.ModelSerializer):

    brand = BrandSummarySerializer(read_only=True)

    categories = serializers.SerializerMethodField()

    primary_image = serializers.SerializerMethodField()

    price_min = serializers.DecimalField(
        max_digits=12,
        decimal_places=2,
        read_only=True,
    )

    price_max = serializers.DecimalField(
        max_digits=12,
        decimal_places=2,
        read_only=True,
    )

    in_stock = serializers.SerializerMethodField()

    class Meta:
        model = Product
        fields = [
            "id",
            "name",
            "slug",
            "brand",
            "categories",
            "base_price",
            "price_min",
            "price_max",
            "primary_image",
            "in_stock",
            "is_active",
            "created_at",
        ]

    def get_categories(self, obj):
        return product_categories_data(obj)

    def get_primary_image(self, obj):
        return product_primary_image_data(obj)

    def get_in_stock(self, obj):
        return product_is_in_stock(obj)


class ProductDetailSerializer(serializers.ModelSerializer):

    brand = BrandSummarySerializer(read_only=True)

    categories = serializers.SerializerMethodField()

    images = ProductImageReadSerializer(
        many=True,
        read_only=True,
    )

    variants = ProductVariantReadSerializer(
        many=True,
        read_only=True,
    )

    price_min = serializers.DecimalField(
        max_digits=12,
        decimal_places=2,
        read_only=True,
    )

    price_max = serializers.DecimalField(
        max_digits=12,
        decimal_places=2,
        read_only=True,
    )

    in_stock = serializers.SerializerMethodField()

    class Meta:
        model = Product
        fields = [
            "id",
            "brand",
            "name",
            "slug",
            "description",
            "base_price",
            "price_min",
            "price_max",
            "categories",
            "images",
            "variants",
            "in_stock",
            "is_active",
            "created_at",
            "updated_at",
        ]

    def get_categories(self, obj):
        return product_categories_data(obj)

    def get_in_stock(self, obj):
        return product_is_in_stock(obj)
