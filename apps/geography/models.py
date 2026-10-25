from decimal import Decimal, ROUND_HALF_UP

from django.core.validators import MinValueValidator
from django.db import models


MONEY_QUANTUM = Decimal("0.01")


class Currency(models.Model):
    """
    Devise utilisée pour l'affichage et la conversion des prix.

    `exchange_rate` représente le nombre d'unités de la devise
    principale nécessaire pour obtenir 1 unité de cette devise.
    Exemple : si XOF est la devise principale, EUR vaut 655.957 XOF.
    """

    code = models.CharField(
        max_length=3,
        unique=True,
    )

    name = models.CharField(
        max_length=100,
    )

    symbol = models.CharField(
        max_length=10,
    )

    exchange_rate = models.DecimalField(
        max_digits=18,
        decimal_places=6,
        default=Decimal("1.000000"),
        validators=[MinValueValidator(Decimal("0.000001"))],
    )

    is_base = models.BooleanField(
        default=False,
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
        db_table = "currencies"
        ordering = ["code"]

        constraints = [
            models.UniqueConstraint(
                fields=["is_base"],
                condition=models.Q(is_base=True),
                name="uq_currencies_single_base",
            ),
        ]

    def save(self, *args, **kwargs):
        self.code = self.code.strip().upper()
        self.name = self.name.strip()
        self.symbol = self.symbol.strip()

        if self.is_base:
            (
                Currency.objects
                .exclude(pk=self.pk)
                .filter(is_base=True)
                .update(is_base=False)
            )
            self.exchange_rate = Decimal("1.000000")

        super().save(*args, **kwargs)

    def convert_from_base(self, amount):
        return (
            Decimal(amount) / self.exchange_rate
        ).quantize(
            MONEY_QUANTUM,
            rounding=ROUND_HALF_UP,
        )

    def convert_to_base(self, amount):
        return (
            Decimal(amount) * self.exchange_rate
        ).quantize(
            MONEY_QUANTUM,
            rounding=ROUND_HALF_UP,
        )

    def __str__(self):
        return f"{self.code} - {self.name}"


class Country(models.Model):
    name = models.CharField(
        max_length=100,
        unique=True,
    )

    code = models.CharField(
        max_length=2,
        unique=True,
        help_text="Code ISO 3166-1 alpha-2.",
    )

    phone_code = models.CharField(
        max_length=10,
        blank=True,
        null=True,
    )

    currency = models.ForeignKey(
        Currency,
        on_delete=models.PROTECT,
        related_name="countries",
        db_column="currency_id",
    )

    payment_methods = models.ManyToManyField(
        "payments.PaymentMethod",
        blank=True,
        related_name="countries",
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
        db_table = "countries"
        ordering = ["name"]

    def save(self, *args, **kwargs):
        self.name = self.name.strip()
        self.code = self.code.strip().upper()
        self.phone_code = (
            self.phone_code.strip()
            if self.phone_code
            else None
        )

        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.name} ({self.code})"
