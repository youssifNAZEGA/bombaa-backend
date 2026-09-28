from django.db import models
from django.core.validators import MinValueValidator

class Category(models.Model):

    name = models.CharField(
        max_length=150,
        unique=True,
    )

    slug = models.SlugField(
        max_length=180,
        unique=True,
    )

    description = models.TextField(
        blank=True,
        null=True,
    )

    parent = models.ForeignKey(
        "self",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="children",
        db_column="parent_id",
    )

    is_active = models.BooleanField(
        default=True,
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
    )

    updated_at = models.DateTimeField(
        auto_now=True,
    )

    class Meta:
        db_table = "categories"
        ordering = ["name"]

    def __str__(self):
        return self.name


class Brand(models.Model):

    name = models.CharField(
        max_length=150,
        unique=True,
    )

    description = models.TextField(
        blank=True,
        null=True,
    )

    logo = models.CharField(
        max_length=500,
        blank=True,
        null=True,
    )

    is_active = models.BooleanField(
        default=True,
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
    )

    updated_at = models.DateTimeField(
        auto_now=True,
    )

    class Meta:
        db_table = "brands"
        ordering = ["name"]

    def __str__(self):
        return self.name

class Product(models.Model):

    brand = models.ForeignKey(
        Brand,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="products",
        db_column="brand_id",
    )

    name = models.CharField(
        max_length=255,
    )

    slug = models.SlugField(
        max_length=255,
        unique=True,
    )

    description = models.TextField(
        blank=True,
        null=True,
    )

    base_price = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        validators=[
            MinValueValidator(0)
        ],
    )

    is_active = models.BooleanField(
        default=True,
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
    )

    updated_at = models.DateTimeField(
        auto_now=True,
    )

    class Meta:
        db_table = "products"
        ordering = ["name"]

    def __str__(self):
        return self.name


class ProductCategory(models.Model):

    product = models.ForeignKey(
        Product,
        on_delete=models.CASCADE,
        db_column="product_id",
        related_name="product_categories",
    )

    category = models.ForeignKey(
        Category,
        on_delete=models.CASCADE,
        db_column="category_id",
        related_name="product_categories",
    )

    pk = models.CompositePrimaryKey(
        "product_id",
        "category_id",
    )

    class Meta:
        db_table = "product_categories"

    def __str__(self):
        return (
            f"{self.product.name} - "
            f"{self.category.name}"
        )

class ProductImage(models.Model):

    product = models.ForeignKey(
        Product,
        on_delete=models.CASCADE,
        related_name="images",
        db_column="product_id",
    )

    image_url = models.CharField(
        max_length=500,
    )

    alt_text = models.CharField(
        max_length=255,
        blank=True,
        null=True,
    )

    is_primary = models.BooleanField(
        default=False,
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
    )

    class Meta:
        db_table = "product_images"
        ordering = ["-is_primary", "created_at"]

    def __str__(self):
        return f"{self.product.name} - {self.image_url}"

class Attribute(models.Model):

    name = models.CharField(
        max_length=100,
        unique=True,
    )

    class Meta:
        db_table = "attributes"
        ordering = ["name"]

    def __str__(self):
        return self.name

class AttributeValue(models.Model):

    attribute = models.ForeignKey(
        Attribute,
        on_delete=models.CASCADE,
        related_name="values",
        db_column="attribute_id",
    )

    value = models.CharField(
        max_length=150,
    )

    class Meta:
        db_table = "attribute_values"
        ordering = ["value"]

        constraints = [
            models.UniqueConstraint(
                fields=["attribute", "value"],
                name="uq_attribute_value",
            )
        ]

    def __str__(self):
        return f"{self.attribute.name} : {self.value}"

class ProductVariant(models.Model):

    product = models.ForeignKey(
        Product,
        on_delete=models.CASCADE,
        related_name="variants",
        db_column="product_id",
    )

    sku = models.CharField(
        max_length=100,
        unique=True,
    )

    price = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        validators=[
            MinValueValidator(0)
        ],
    )

    is_active = models.BooleanField(
        default=True,
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
    )

    updated_at = models.DateTimeField(
        auto_now=True,
    )

    class Meta:
        db_table = "product_variants"
        ordering = ["sku"]

    def __str__(self):
        return self.sku

class VariantAttributeValue(models.Model):

    variant = models.ForeignKey(
        ProductVariant,
        on_delete=models.CASCADE,
        db_column="variant_id",
        related_name="variant_attribute_values",
    )

    attribute_value = models.ForeignKey(
        AttributeValue,
        on_delete=models.CASCADE,
        db_column="attribute_value_id",
        related_name="variant_attribute_values",
    )

    pk = models.CompositePrimaryKey(
        "variant_id",
        "attribute_value_id",
    )

    class Meta:
        db_table = "variant_attribute_values"

    def __str__(self):
        return (
            f"{self.variant.sku} - "
            f"{self.attribute_value.attribute.name}: "
            f"{self.attribute_value.value}"
        )