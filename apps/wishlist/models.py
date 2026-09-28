from django.db import models

from apps.accounts.models import User


class Wishlist(models.Model):
    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name="wishlist",
        db_column="user_id",
    )

    created_at = models.DateTimeField(
        auto_now_add=True
    )

    updated_at = models.DateTimeField(
        auto_now=True
    )

    class Meta:
        db_table = "wishlists"

    def __str__(self):
        return f"Wishlist de {self.user.email}"


class WishlistItem(models.Model):
    wishlist = models.ForeignKey(
        Wishlist,
        on_delete=models.CASCADE,
        related_name="items",
        db_column="wishlist_id",
    )

    variant = models.ForeignKey(
        "catalog.ProductVariant",
        on_delete=models.CASCADE,
        related_name="wishlist_items",
        db_column="variant_id",
    )

    created_at = models.DateTimeField(
        auto_now_add=True
    )

    class Meta:
        db_table = "wishlist_items"
        constraints = [
            models.UniqueConstraint(
                fields=["wishlist", "variant"],
                name="uq_wishlist_item_variant",
            ),
        ]

    def __str__(self):
        return (
            f"{self.wishlist.user.email} - "
            f"{self.variant.sku}"
        )