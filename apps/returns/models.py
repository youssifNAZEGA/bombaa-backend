from decimal import Decimal
from uuid import uuid4

from django.core.validators import MinValueValidator
from django.db import models


class ReturnRequest(models.Model):
    """
    Demande de retour portant sur un ou plusieurs articles
    d'une commande livrée.
    """

    class Status(models.TextChoices):
        REQUESTED = "REQUESTED", "Demandé"
        APPROVED = "APPROVED", "Approuvé"
        RECEIVED = "RECEIVED", "Reçu"
        REJECTED = "REJECTED", "Rejeté"
        CANCELLED = "CANCELLED", "Annulé"
        REFUNDED = "REFUNDED", "Remboursé"

    reference = models.CharField(
        max_length=30,
        unique=True,
        editable=False,
    )

    order = models.ForeignKey(
        "orders.Order",
        on_delete=models.PROTECT,
        related_name="return_requests",
        db_column="order_id",
    )

    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.REQUESTED,
    )

    reason = models.TextField()

    admin_note = models.TextField(
        blank=True,
        null=True,
    )

    total_amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal("0.00"),
        validators=[
            MinValueValidator(Decimal("0.00"))
        ],
    )

    currency = models.CharField(
        max_length=3,
        default="XOF",
    )

    processed_by = models.ForeignKey(
        "accounts.User",
        on_delete=models.SET_NULL,
        related_name="processed_return_requests",
        db_column="processed_by_id",
        blank=True,
        null=True,
    )

    approved_at = models.DateTimeField(
        blank=True,
        null=True,
    )

    received_at = models.DateTimeField(
        blank=True,
        null=True,
    )

    rejected_at = models.DateTimeField(
        blank=True,
        null=True,
    )

    cancelled_at = models.DateTimeField(
        blank=True,
        null=True,
    )

    refunded_at = models.DateTimeField(
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
        db_table = "return_requests"
        ordering = ["-created_at"]
        indexes = [
            models.Index(
                fields=["status", "-created_at"],
                name="idx_returns_status_created",
            ),
            models.Index(
                fields=["order", "-created_at"],
                name="idx_returns_order_created",
            ),
        ]

    @classmethod
    def generate_reference(cls):
        while True:
            reference = f"RET-{uuid4().hex[:8].upper()}"

            if not cls.objects.filter(
                reference=reference
            ).exists():
                return reference

    def save(self, *args, **kwargs):
        if not self.reference:
            self.reference = self.generate_reference()

        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.reference} - {self.order.reference}"


class ReturnItem(models.Model):
    """
    Ligne d'une demande de retour.

    Les montants et libellés sont figés au moment de la demande
    pour conserver l'historique.
    """

    return_request = models.ForeignKey(
        ReturnRequest,
        on_delete=models.CASCADE,
        related_name="items",
        db_column="return_request_id",
    )

    order_item = models.ForeignKey(
        "orders.OrderItem",
        on_delete=models.PROTECT,
        related_name="return_items",
        db_column="order_item_id",
    )

    product_name = models.CharField(
        max_length=255,
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
        validators=[
            MinValueValidator(Decimal("0.00"))
        ],
    )

    subtotal = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        validators=[
            MinValueValidator(Decimal("0.00"))
        ],
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
    )

    class Meta:
        db_table = "return_items"
        ordering = ["id"]
        constraints = [
            models.UniqueConstraint(
                fields=["return_request", "order_item"],
                name="uq_return_item_order_item",
            ),
        ]
        indexes = [
            models.Index(
                fields=["return_request"],
                name="idx_return_items_request",
            ),
        ]

    def __str__(self):
        return (
            f"{self.return_request.reference} - "
            f"{self.sku} x{self.quantity}"
        )


class Refund(models.Model):
    """
    Remboursement demandé ou traité pour une commande.

    Le remboursement peut être lié à une demande de retour ou
    être créé directement par le service financier.
    """

    class Status(models.TextChoices):
        PENDING = "PENDING", "En attente"
        APPROVED = "APPROVED", "Approuvé"
        PROCESSED = "PROCESSED", "Traité"
        REJECTED = "REJECTED", "Rejeté"
        CANCELLED = "CANCELLED", "Annulé"

    class Method(models.TextChoices):
        ORIGINAL_PAYMENT = (
            "ORIGINAL_PAYMENT",
            "Moyen de paiement d'origine",
        )
        MOBILE_MONEY = "MOBILE_MONEY", "Mobile Money"
        BANK_TRANSFER = "BANK_TRANSFER", "Virement bancaire"
        CASH = "CASH", "Espèces"
        OTHER = "OTHER", "Autre"

    reference = models.CharField(
        max_length=30,
        unique=True,
        editable=False,
    )

    order = models.ForeignKey(
        "orders.Order",
        on_delete=models.PROTECT,
        related_name="refunds",
        db_column="order_id",
    )

    return_request = models.ForeignKey(
        ReturnRequest,
        on_delete=models.SET_NULL,
        related_name="refunds",
        db_column="return_request_id",
        blank=True,
        null=True,
    )

    payment = models.ForeignKey(
        "payments.Payment",
        on_delete=models.PROTECT,
        related_name="refunds",
        db_column="payment_id",
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

    reason = models.TextField()

    method = models.CharField(
        max_length=30,
        choices=Method.choices,
        default=Method.ORIGINAL_PAYMENT,
    )

    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
    )

    external_reference = models.CharField(
        max_length=150,
        blank=True,
        null=True,
    )

    notes = models.TextField(
        blank=True,
        null=True,
    )

    requested_by = models.ForeignKey(
        "accounts.User",
        on_delete=models.SET_NULL,
        related_name="requested_refunds",
        db_column="requested_by_id",
        blank=True,
        null=True,
    )

    processed_by = models.ForeignKey(
        "accounts.User",
        on_delete=models.SET_NULL,
        related_name="processed_refunds",
        db_column="processed_by_id",
        blank=True,
        null=True,
    )

    approved_at = models.DateTimeField(
        blank=True,
        null=True,
    )

    processed_at = models.DateTimeField(
        blank=True,
        null=True,
    )

    rejected_at = models.DateTimeField(
        blank=True,
        null=True,
    )

    requested_at = models.DateTimeField(
        auto_now_add=True,
    )

    updated_at = models.DateTimeField(
        auto_now=True,
    )

    class Meta:
        db_table = "refunds"
        ordering = ["-requested_at"]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(amount__gt=0),
                name="chk_refunds_amount",
            ),
        ]
        indexes = [
            models.Index(
                fields=["status", "-requested_at"],
                name="idx_refunds_status_created",
            ),
            models.Index(
                fields=["order", "-requested_at"],
                name="idx_refunds_order_created",
            ),
        ]

    @classmethod
    def generate_reference(cls):
        while True:
            reference = f"REF-{uuid4().hex[:8].upper()}"

            if not cls.objects.filter(
                reference=reference
            ).exists():
                return reference

    def save(self, *args, **kwargs):
        if not self.reference:
            self.reference = type(self).generate_reference()

        super().save(*args, **kwargs)

    def __str__(self):
        return (
            f"{self.reference} - {self.amount} "
            f"{self.currency}"
        )
