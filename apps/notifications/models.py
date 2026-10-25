from django.db import models
from django.utils import timezone


class Notification(models.Model):

    class Event(models.TextChoices):
        ORDER_CREATED = (
            "ORDER_CREATED",
            "Création d'une commande",
        )
        ORDER_CONFIRMED = (
            "ORDER_CONFIRMED",
            "Confirmation d'une commande",
        )
        PAYMENT_CONFIRMED = (
            "PAYMENT_CONFIRMED",
            "Confirmation d'un paiement",
        )
        PAYMENT_FAILED = (
            "PAYMENT_FAILED",
            "Échec d'un paiement",
        )
        ORDER_PROCESSING = (
            "ORDER_PROCESSING",
            "Préparation d'une commande",
        )
        ORDER_SHIPPED = (
            "ORDER_SHIPPED",
            "Expédition d'une commande",
        )
        ORDER_DELIVERED = (
            "ORDER_DELIVERED",
            "Livraison d'une commande",
        )
        ORDER_CANCELLED = (
            "ORDER_CANCELLED",
            "Annulation d'une commande",
        )
        REFUND = (
            "REFUND",
            "Remboursement",
        )
        PROMOTION = (
            "PROMOTION",
            "Promotion",
        )
        NEW_PRODUCT = (
            "NEW_PRODUCT",
            "Nouveau produit",
        )
        BACK_IN_STOCK = (
            "BACK_IN_STOCK",
            "Retour en stock",
        )
        NEW_COUPON = (
            "NEW_COUPON",
            "Nouveau coupon",
        )

    class Channel(models.TextChoices):
        IN_APP = "IN_APP", "Dans l'application"
        PUSH = "PUSH", "Notification push"
        EMAIL = "EMAIL", "Email"
        SMS = "SMS", "SMS"

    user = models.ForeignKey(
        "accounts.User",
        on_delete=models.CASCADE,
        related_name="notifications",
        db_column="user_id",
    )

    event = models.CharField(
        max_length=30,
        choices=Event.choices,
    )

    channel = models.CharField(
        max_length=20,
        choices=Channel.choices,
        default=Channel.IN_APP,
    )

    title = models.CharField(
        max_length=255,
    )

    message = models.TextField()

    order = models.ForeignKey(
        "orders.Order",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="notifications",
        db_column="order_id",
    )

    product = models.ForeignKey(
        "catalog.Product",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="notifications",
        db_column="product_id",
    )

    data = models.JSONField(
        default=dict,
        blank=True,
    )

    is_read = models.BooleanField(
        default=False,
    )

    read_at = models.DateTimeField(
        blank=True,
        null=True,
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
    )

    class Meta:
        db_table = "notifications"
        ordering = ["-created_at"]
        indexes = [
            models.Index(
                fields=["user", "is_read", "-created_at"],
                name="idx_notifications_user_read",
            ),
            models.Index(
                fields=["event"],
                name="idx_notifications_event",
            ),
        ]

    def mark_as_read(self):
        if self.is_read:
            return self

        self.is_read = True
        self.read_at = timezone.now()
        self.save(
            update_fields=[
                "is_read",
                "read_at",
            ]
        )

        return self

    def __str__(self):
        return f"{self.user.email} - {self.title}"


class NotificationPreference(models.Model):

    user = models.OneToOneField(
        "accounts.User",
        on_delete=models.CASCADE,
        related_name="notification_preferences",
        db_column="user_id",
    )

    in_app_enabled = models.BooleanField(
        default=True,
    )

    email_enabled = models.BooleanField(
        default=False,
    )

    sms_enabled = models.BooleanField(
        default=False,
    )

    push_enabled = models.BooleanField(
        default=False,
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
    )

    updated_at = models.DateTimeField(
        auto_now=True,
    )

    class Meta:
        db_table = "notification_preferences"

    def __str__(self):
        return f"Préférences de {self.user.email}"
