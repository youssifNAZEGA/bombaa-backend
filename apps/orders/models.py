from decimal import Decimal

from django.core.validators import MinValueValidator
from django.db import models

from apps.accounts.models import User


class Order(models.Model):
    class Status(models.TextChoices):
        PENDING = "PENDING", "En attente"
        CONFIRMED = "CONFIRMED", "Confirmée"
        PROCESSING = "PROCESSING", "En préparation"
        SHIPPED = "SHIPPED", "Expédiée"
        DELIVERED = "DELIVERED", "Livrée"
        CANCELLED = "CANCELLED", "Annulée"
        COMPLETED = "COMPLETED", "Terminée"

    user = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        related_name="orders",
        db_column="user_id",
    )

    reference = models.CharField(
        max_length=50,
        unique=True,
    )

    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
    )

    subtotal = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        validators=[MinValueValidator(Decimal("0.00"))],
    )

    shipping_cost = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal("0.00"),
        validators=[MinValueValidator(Decimal("0.00"))],
    )

    discount_amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal("0.00"),
        validators=[MinValueValidator(Decimal("0.00"))],
    )

    total_amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        validators=[MinValueValidator(Decimal("0.00"))],
    )

    currency = models.CharField(
        max_length=3,
        default="XOF",
    )

    notes = models.TextField(
        blank=True,
        null=True,
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
    )

    updated_at = models.DateTimeField(
        auto_now=True,
    )

    class Meta:
        db_table = "orders"
        ordering = ["-created_at"]

    def __str__(self):
        return self.reference


class OrderAddress(models.Model):
    order = models.OneToOneField(
        Order,
        on_delete=models.CASCADE,
        related_name="shipping_address",
        db_column="order_id",
    )

    recipient_name = models.CharField(
        max_length=200,
    )

    phone = models.CharField(
        max_length=30,
    )

    address_line1 = models.CharField(
        max_length=255,
    )

    address_line2 = models.CharField(
        max_length=255,
        blank=True,
        null=True,
    )

    city = models.CharField(
        max_length=100,
    )

    state = models.CharField(
        max_length=100,
        blank=True,
        null=True,
    )

    postal_code = models.CharField(
        max_length=30,
        blank=True,
        null=True,
    )

    country_name = models.CharField(
        max_length=100,
    )

    country_code = models.CharField(
        max_length=10,
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
    )

    class Meta:
        db_table = "order_addresses"

    def __str__(self):
        return f"{self.recipient_name} - {self.city}"


class OrderItem(models.Model):
    order = models.ForeignKey(
        Order,
        on_delete=models.CASCADE,
        related_name="items",
        db_column="order_id",
    )

    variant = models.ForeignKey(
        "catalog.ProductVariant",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="order_items",
        db_column="variant_id",
    )

    product_name = models.CharField(
        max_length=255,
    )

    variant_description = models.CharField(
        max_length=255,
        blank=True,
        null=True,
    )

    sku = models.CharField(
        max_length=100,
    )

    quantity = models.PositiveIntegerField(
        validators=[MinValueValidator(1)],
    )

    unit_price = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        validators=[MinValueValidator(Decimal("0.00"))],
    )

    subtotal = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        validators=[MinValueValidator(Decimal("0.00"))],
    )

    class Meta:
        db_table = "order_items"
        ordering = ["id"]

    def __str__(self):
        return f"{self.order.reference} - {self.sku}"