from django.core.validators import MinValueValidator
from django.db import models
from decimal import Decimal

from apps.orders.models import Order


class PaymentMethod(models.Model):
    name = models.CharField(max_length=100)

    code = models.CharField(
        max_length=50,
        unique=True,
    )

    description = models.TextField(
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
        db_table = "payment_methods"
        ordering = ["name"]

    def __str__(self):
        return f"{self.name} ({self.code})"


class Payment(models.Model):

    class Status(models.TextChoices):
        PENDING = "PENDING", "En attente"
        PROCESSING = "PROCESSING", "En traitement"
        SUCCESS = "SUCCESS", "Réussi"
        FAILED = "FAILED", "Échoué"
        CANCELLED = "CANCELLED", "Annulé"
        REFUNDED = "REFUNDED", "Remboursé"

    order = models.ForeignKey(
        Order,
        on_delete=models.PROTECT,
        related_name="payments",
        db_column="order_id",
    )

    payment_method = models.ForeignKey(
        PaymentMethod,
        on_delete=models.PROTECT,
        related_name="payments",
        db_column="payment_method_id",
    )

    reference = models.CharField(
        max_length=100,
        unique=True,
    )

    amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        validators=[
            MinValueValidator(Decimal("0.01"))
        ],
    )

    currency = models.CharField(
        max_length=3,
    )

    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
    )

    paid_at = models.DateTimeField(
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
        db_table = "payments"
        ordering = ["-created_at"]

        constraints = [
            models.CheckConstraint(
                condition=models.Q(amount__gt=0),
                name="chk_payments_amount",
            ),
        ]

    def __str__(self):
        return f"{self.reference} - {self.amount} {self.currency}"


class Transaction(models.Model):

    class Status(models.TextChoices):
        PENDING = "PENDING", "En attente"
        SUCCESS = "SUCCESS", "Réussi"
        FAILED = "FAILED", "Échoué"
        CANCELLED = "CANCELLED", "Annulé"
        REFUNDED = "REFUNDED", "Remboursé"

    payment = models.ForeignKey(
        Payment,
        on_delete=models.CASCADE,
        related_name="transactions",
        db_column="payment_id",
    )

    reference = models.CharField(
        max_length=100,
        unique=True,
    )

    external_reference = models.CharField(
        max_length=150,
        blank=True,
        null=True,
    )

    amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        validators=[
            MinValueValidator(Decimal("0.01"))
        ],
    )

    currency = models.CharField(
        max_length=3,
    )

    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
    )

    transaction_date = models.DateTimeField(
        auto_now_add=True,
    )

    response_message = models.TextField(
        blank=True,
        null=True,
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
    )

    class Meta:
        db_table = "transactions"
        ordering = ["-transaction_date"]

        constraints = [
            models.CheckConstraint(
                condition=models.Q(amount__gt=0),
                name="chk_transactions_amount",
            ),
        ]

    def __str__(self):
        return f"{self.reference} - {self.status}"