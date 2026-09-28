from django.db import models
from django.core.validators import MinValueValidator


class Stock(models.Model):
    variant = models.OneToOneField(
        "catalog.ProductVariant",
        on_delete=models.CASCADE,
        related_name="stock",
        db_column="variant_id",
    )

    quantity = models.IntegerField(
        default=0,
        validators=[MinValueValidator(0)],
    )

    reserved_quantity = models.IntegerField(
        default=0,
        validators=[MinValueValidator(0)],
    )

    minimum_quantity = models.IntegerField(
        default=0,
        validators=[MinValueValidator(0)],
    )

    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "stocks"
        constraints = [
            models.CheckConstraint(
                condition=models.Q(quantity__gte=0),
                name="chk_stocks_quantity",
            ),
            models.CheckConstraint(
                condition=models.Q(reserved_quantity__gte=0),
                name="chk_stocks_reserved_quantity",
            ),
            models.CheckConstraint(
                condition=models.Q(minimum_quantity__gte=0),
                name="chk_stocks_minimum_quantity",
            ),
            models.CheckConstraint(
                condition=models.Q(
                    reserved_quantity__lte=models.F("quantity")
                ),
                name="chk_stocks_reserved_less_than_quantity",
            ),
        ]

    def __str__(self):
        return f"{self.variant.sku} - Stock: {self.quantity}"



class StockMovement(models.Model):
    MOVEMENT_IN = "IN"
    MOVEMENT_OUT = "OUT"
    MOVEMENT_ADJUSTMENT = "ADJUSTMENT"

    MOVEMENT_TYPES = [
        (MOVEMENT_IN, "Entrée"),
        (MOVEMENT_OUT, "Sortie"),
        (MOVEMENT_ADJUSTMENT, "Ajustement"),
    ]

    stock = models.ForeignKey(
        Stock,
        on_delete=models.CASCADE,
        related_name="movements",
        db_column="stock_id",
    )

    movement_type = models.CharField(
        max_length=20,
        choices=MOVEMENT_TYPES,
    )

    quantity = models.IntegerField(
        validators=[MinValueValidator(1)],
    )

    reason = models.CharField(
        max_length=255,
        blank=True,
        null=True,
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
    )

    class Meta:
        db_table = "stock_movements"
        ordering = ["-created_at"]

    def __str__(self):
        return (
            f"{self.stock.variant.sku} - "
            f"{self.movement_type} - "
            f"{self.quantity}"
        )