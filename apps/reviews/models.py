from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.utils import timezone


class Review(models.Model):
    """
    Avis laissé par un client après l'achat d'un produit.

    Un avis est créé en attente de modération. Seuls les avis
    approuvés sont visibles publiquement et comptent dans la
    moyenne du produit.
    """

    class Status(models.TextChoices):
        PENDING = "PENDING", "En attente"
        APPROVED = "APPROVED", "Approuvé"
        REJECTED = "REJECTED", "Rejeté"

    product = models.ForeignKey(
        "catalog.Product",
        on_delete=models.CASCADE,
        related_name="reviews",
        db_column="product_id",
    )

    user = models.ForeignKey(
        "accounts.User",
        on_delete=models.CASCADE,
        related_name="reviews",
        db_column="user_id",
    )

    order_item = models.ForeignKey(
        "orders.OrderItem",
        on_delete=models.SET_NULL,
        related_name="reviews",
        db_column="order_item_id",
        blank=True,
        null=True,
        help_text=(
            "Article de commande qui justifie l'achat vérifié."
        ),
    )

    rating = models.PositiveSmallIntegerField(
        validators=[
            MinValueValidator(1),
            MaxValueValidator(5),
        ],
    )

    comment = models.TextField(
        blank=True,
        null=True,
    )

    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
    )

    is_verified_purchase = models.BooleanField(
        default=False,
    )

    moderated_by = models.ForeignKey(
        "accounts.User",
        on_delete=models.SET_NULL,
        related_name="moderated_reviews",
        db_column="moderated_by_id",
        blank=True,
        null=True,
    )

    moderated_at = models.DateTimeField(
        blank=True,
        null=True,
    )

    moderation_note = models.TextField(
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
        db_table = "reviews"
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["user", "product"],
                name="uq_review_user_product",
            ),
        ]
        indexes = [
            models.Index(
                fields=["product", "status", "-created_at"],
                name="idx_reviews_product_status",
            ),
            models.Index(
                fields=["user", "-created_at"],
                name="idx_reviews_user_created",
            ),
            models.Index(
                fields=["status", "-created_at"],
                name="idx_reviews_status_created",
            ),
        ]

    def approve(self, *, moderator, note=None):
        self.status = self.Status.APPROVED
        self.moderated_by = moderator
        self.moderated_at = timezone.now()
        self.moderation_note = note
        self.save(
            update_fields=[
                "status",
                "moderated_by",
                "moderated_at",
                "moderation_note",
                "updated_at",
            ]
        )
        return self

    def reject(self, *, moderator, note=None):
        self.status = self.Status.REJECTED
        self.moderated_by = moderator
        self.moderated_at = timezone.now()
        self.moderation_note = note
        self.save(
            update_fields=[
                "status",
                "moderated_by",
                "moderated_at",
                "moderation_note",
                "updated_at",
            ]
        )
        return self

    def __str__(self):
        return (
            f"{self.product.name} - {self.user.email} - "
            f"{self.rating}/5"
        )


class ReviewImage(models.Model):
    review = models.ForeignKey(
        Review,
        on_delete=models.CASCADE,
        related_name="images",
        db_column="review_id",
    )

    image_url = models.CharField(
        max_length=500,
    )

    alt_text = models.CharField(
        max_length=255,
        blank=True,
        null=True,
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
    )

    class Meta:
        db_table = "review_images"
        ordering = ["created_at"]
        indexes = [
            models.Index(
                fields=["review"],
                name="idx_review_images_review",
            ),
        ]

    def __str__(self):
        return f"{self.review_id} - {self.image_url}"
