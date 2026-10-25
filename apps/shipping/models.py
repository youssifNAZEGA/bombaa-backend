from decimal import Decimal

from django.core.validators import MinValueValidator
from django.db import models


class ShippingZone(models.Model):
    name = models.CharField(
        max_length=150,
        unique=True,
    )

    description = models.TextField(
        blank=True,
        null=True,
    )

    countries = models.ManyToManyField(
        "geography.Country",
        blank=True,
        related_name="shipping_zones",
        help_text=(
            "Laisser vide pour une zone internationale "
            "applicable à tous les pays."
        ),
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
        db_table = "shipping_zones"
        ordering = ["name"]

    def __str__(self):
        return self.name


class ShippingMethod(models.Model):
    name = models.CharField(
        max_length=150,
    )

    code = models.CharField(
        max_length=50,
        unique=True,
    )

    description = models.TextField(
        blank=True,
        null=True,
    )

    carrier = models.CharField(
        max_length=150,
        blank=True,
        null=True,
    )

    estimated_days = models.PositiveSmallIntegerField(
        default=3,
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
        db_table = "shipping_methods"
        ordering = ["name"]

    def save(self, *args, **kwargs):
        self.name = self.name.strip()
        self.code = self.code.strip().upper()
        self.carrier = (
            self.carrier.strip()
            if self.carrier
            else None
        )

        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.name} ({self.code})"


class ShippingRate(models.Model):
    zone = models.ForeignKey(
        ShippingZone,
        on_delete=models.CASCADE,
        related_name="rates",
        db_column="shipping_zone_id",
    )

    method = models.ForeignKey(
        ShippingMethod,
        on_delete=models.CASCADE,
        related_name="rates",
        db_column="shipping_method_id",
    )

    min_weight_grams = models.PositiveIntegerField(
        default=0,
    )

    max_weight_grams = models.PositiveIntegerField(
        blank=True,
        null=True,
        help_text=(
            "Laisser vide pour un tarif sans limite supérieure."
        ),
    )

    price = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        validators=[MinValueValidator(Decimal("0.00"))],
    )

    currency = models.ForeignKey(
        "geography.Currency",
        on_delete=models.PROTECT,
        related_name="shipping_rates",
        db_column="currency_id",
        blank=True,
        null=True,
        help_text=(
            "Laisser vide pour utiliser la devise principale."
        ),
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
        db_table = "shipping_rates"
        ordering = ["zone__name", "method__name", "min_weight_grams"]

        constraints = [
            models.CheckConstraint(
                condition=(
                    models.Q(max_weight_grams__isnull=True)
                    | models.Q(
                        max_weight_grams__gte=models.F(
                            "min_weight_grams"
                        )
                    )
                ),
                name="chk_shipping_rates_weight_range",
            ),
        ]

    def __str__(self):
        return (
            f"{self.zone.name} - {self.method.name} - "
            f"{self.price} {self.currency_id or 'base'}"
        )


class Delivery(models.Model):
    class Status(models.TextChoices):
        PENDING = "PENDING", "En attente"
        PREPARING = "PREPARING", "En préparation"
        SHIPPED = "SHIPPED", "Expédiée"
        IN_TRANSIT = "IN_TRANSIT", "En transit"
        DELIVERED = "DELIVERED", "Livrée"
        FAILED = "FAILED", "Échec"
        RETURNED = "RETURNED", "Retournée"

    order = models.OneToOneField(
        "orders.Order",
        on_delete=models.CASCADE,
        related_name="delivery",
        db_column="order_id",
    )

    shipping_method = models.ForeignKey(
        ShippingMethod,
        on_delete=models.PROTECT,
        related_name="deliveries",
        db_column="shipping_method_id",
        blank=True,
        null=True,
    )

    tracking_number = models.CharField(
        max_length=150,
        blank=True,
        null=True,
    )

    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
    )

    shipped_at = models.DateTimeField(
        blank=True,
        null=True,
    )

    delivered_at = models.DateTimeField(
        blank=True,
        null=True,
    )

    estimated_delivery_date = models.DateField(
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
        db_table = "deliveries"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.order.reference} - {self.status}"
