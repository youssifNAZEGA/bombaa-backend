from decimal import Decimal, ROUND_HALF_UP

from django.core.validators import MinValueValidator
from django.db import models
from django.utils import timezone


MONEY_QUANTUM = Decimal("0.01")


class DiscountType(models.TextChoices):
    PERCENTAGE = "PERCENTAGE", "Pourcentage"
    FIXED = "FIXED", "Montant fixe"


class Promotion(models.Model):
    """
    Promotion appliquée automatiquement au panier.

    Une promotion peut cibler des produits, des catégories et/ou
    des marques. Si aucun ciblage produit n'est renseigné, elle
    s'applique à tout le catalogue. Les pays vides signifient tous
    les pays.
    """

    name = models.CharField(
        max_length=150,
    )

    description = models.TextField(
        blank=True,
        null=True,
    )

    discount_type = models.CharField(
        max_length=20,
        choices=DiscountType.choices,
        default=DiscountType.PERCENTAGE,
    )

    value = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        validators=[MinValueValidator(Decimal("0.01"))],
    )

    starts_at = models.DateTimeField(
        blank=True,
        null=True,
    )

    ends_at = models.DateTimeField(
        blank=True,
        null=True,
    )

    is_active = models.BooleanField(
        default=True,
    )

    products = models.ManyToManyField(
        "catalog.Product",
        blank=True,
        related_name="promotions",
    )

    categories = models.ManyToManyField(
        "catalog.Category",
        blank=True,
        related_name="promotions",
    )

    brands = models.ManyToManyField(
        "catalog.Brand",
        blank=True,
        related_name="promotions",
    )

    countries = models.ManyToManyField(
        "geography.Country",
        blank=True,
        related_name="promotions",
        help_text=(
            "Laisser vide pour rendre la promotion disponible "
            "dans tous les pays."
        ),
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
    )

    updated_at = models.DateTimeField(
        auto_now=True,
    )

    class Meta:
        db_table = "promotions"
        ordering = ["-created_at"]
        indexes = [
            models.Index(
                fields=["is_active", "starts_at", "ends_at"],
                name="idx_promotions_active_dates",
            ),
        ]

    def is_running(self, at=None):
        at = at or timezone.now()

        if not self.is_active:
            return False

        if self.starts_at is not None and at < self.starts_at:
            return False

        if self.ends_at is not None and at > self.ends_at:
            return False

        return True

    def calculate_discount(self, amount):
        amount = Decimal(str(amount or "0.00"))

        if amount <= 0 or self.value <= 0:
            return Decimal("0.00")

        if self.discount_type == DiscountType.PERCENTAGE:
            discount = amount * self.value / Decimal("100")
        else:
            discount = Decimal(self.value)

        discount = min(discount, amount)

        return discount.quantize(
            MONEY_QUANTUM,
            rounding=ROUND_HALF_UP,
        )

    def __str__(self):
        return self.name


class Coupon(models.Model):
    """
    Coupon de réduction utilisé par un client au panier.

    Le code est unique et peut être généré automatiquement par
    l'API. Le nombre d'utilisations est calculé à partir des
    utilisations actives (non libérées par une annulation).
    """

    code = models.CharField(
        max_length=50,
        unique=True,
    )

    description = models.TextField(
        blank=True,
        null=True,
    )

    discount_type = models.CharField(
        max_length=20,
        choices=DiscountType.choices,
        default=DiscountType.PERCENTAGE,
    )

    value = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        validators=[MinValueValidator(Decimal("0.01"))],
    )

    starts_at = models.DateTimeField(
        blank=True,
        null=True,
    )

    ends_at = models.DateTimeField(
        blank=True,
        null=True,
    )

    minimum_amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal("0.00"),
        validators=[MinValueValidator(Decimal("0.00"))],
    )

    max_uses = models.PositiveIntegerField(
        blank=True,
        null=True,
        help_text=(
            "Laisser vide pour un nombre d'utilisations illimité."
        ),
    )

    is_active = models.BooleanField(
        default=True,
    )

    products = models.ManyToManyField(
        "catalog.Product",
        blank=True,
        related_name="coupons",
    )

    categories = models.ManyToManyField(
        "catalog.Category",
        blank=True,
        related_name="coupons",
    )

    countries = models.ManyToManyField(
        "geography.Country",
        blank=True,
        related_name="coupons",
        help_text=(
            "Laisser vide pour rendre le coupon disponible "
            "dans tous les pays."
        ),
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
    )

    updated_at = models.DateTimeField(
        auto_now=True,
    )

    class Meta:
        db_table = "coupons"
        ordering = ["-created_at"]
        indexes = [
            models.Index(
                fields=["is_active", "starts_at", "ends_at"],
                name="idx_coupons_active_dates",
            ),
        ]

    def save(self, *args, **kwargs):
        self.code = str(self.code or "").strip().upper()

        super().save(*args, **kwargs)

    def is_running(self, at=None):
        at = at or timezone.now()

        if not self.is_active:
            return False

        if self.starts_at is not None and at < self.starts_at:
            return False

        if self.ends_at is not None and at > self.ends_at:
            return False

        return True

    @property
    def current_uses(self):
        return self.redemptions.filter(
            released_at__isnull=True
        ).count()

    @property
    def remaining_uses(self):
        if self.max_uses is None:
            return None

        return max(self.max_uses - self.current_uses, 0)

    def calculate_discount(self, amount):
        amount = Decimal(str(amount or "0.00"))

        if amount <= 0 or self.value <= 0:
            return Decimal("0.00")

        if self.discount_type == DiscountType.PERCENTAGE:
            discount = amount * self.value / Decimal("100")
        else:
            discount = Decimal(self.value)

        discount = min(discount, amount)

        return discount.quantize(
            MONEY_QUANTUM,
            rounding=ROUND_HALF_UP,
        )

    def __str__(self):
        return self.code


class CouponRedemption(models.Model):
    """
    Trace l'utilisation d'un coupon par une commande.

    `released_at` est renseigné lorsqu'une commande est annulée :
    l'utilisation redevient alors disponible.
    """

    coupon = models.ForeignKey(
        Coupon,
        on_delete=models.PROTECT,
        related_name="redemptions",
        db_column="coupon_id",
    )

    user = models.ForeignKey(
        "accounts.User",
        on_delete=models.PROTECT,
        related_name="coupon_redemptions",
        db_column="user_id",
    )

    order = models.OneToOneField(
        "orders.Order",
        on_delete=models.CASCADE,
        related_name="coupon_redemption",
        db_column="order_id",
    )

    discount_amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        validators=[MinValueValidator(Decimal("0.00"))],
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
    )

    released_at = models.DateTimeField(
        blank=True,
        null=True,
    )

    class Meta:
        db_table = "coupon_redemptions"
        ordering = ["-created_at"]
        indexes = [
            models.Index(
                fields=["coupon", "released_at"],
                name="idx_coupon_redemptions_active",
            ),
        ]

    def __str__(self):
        return f"{self.coupon.code} - {self.order.reference}"
