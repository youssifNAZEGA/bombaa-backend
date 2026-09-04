from django.db import models

from apps.accounts.models import User


class Address(models.Model):

    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="addresses",
        db_column="user_id",
    )

    label = models.CharField(
        max_length=100,
        blank=True,
        null=True,
    )

    first_name = models.CharField(
        max_length=100,
    )

    last_name = models.CharField(
        max_length=100,
    )

    phone = models.CharField(
        max_length=30,
    )

    address_line_1 = models.CharField(
        max_length=255,
    )

    address_line_2 = models.CharField(
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

    country = models.CharField(
        max_length=100,
    )

    is_default = models.BooleanField(
        default=False,
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
    )

    updated_at = models.DateTimeField(
        auto_now=True,
    )

    class Meta:
        db_table = "addresses"
        ordering = ["-is_default", "-created_at"]

    def __str__(self):
        return (
            f"{self.first_name} {self.last_name} - "
            f"{self.city}, {self.country}"
        )