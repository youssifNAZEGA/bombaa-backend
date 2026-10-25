from dataclasses import dataclass, field
from decimal import Decimal, ROUND_HALF_UP
from uuid import uuid4

from django.db.models import Q
from django.utils import timezone

from apps.promotions.models import (
    Coupon,
    CouponRedemption,
    Promotion,
)


MONEY_QUANTUM = Decimal("0.01")


def money(value):
    return Decimal(str(value or "0.00")).quantize(
        MONEY_QUANTUM,
        rounding=ROUND_HALF_UP,
    )


def targets_product(discount, product):
    """
    Vérifie si une promotion ou un coupon cible un produit.

    Les cibles produits, catégories et marques sont combinées
    avec un OU. Une remise sans aucune cible s'applique à tout
    le catalogue.
    """

    product_targets = {
        item.id
        for item in discount.products.all()
    }
    category_targets = {
        item.id
        for item in discount.categories.all()
    }
    brand_targets = set()

    if hasattr(discount, "brands"):
        brand_targets = {
            item.id
            for item in discount.brands.all()
        }

    if not (
        product_targets
        or category_targets
        or brand_targets
    ):
        return True

    if product.id in product_targets:
        return True

    if product.brand_id and product.brand_id in brand_targets:
        return True

    if category_targets:
        product_category_ids = {
            item.category_id
            for item in product.product_categories.all()
        }

        if product_category_ids & category_targets:
            return True

    return False


def applies_to_country(discount, country):
    country_targets = {
        item.id
        for item in discount.countries.all()
    }

    if not country_targets:
        return True

    if country is None:
        return False

    return country.id in country_targets


class PromotionService:
    @classmethod
    def active_promotions(cls, *, country=None, at=None):
        at = at or timezone.now()

        queryset = (
            Promotion.objects
            .filter(is_active=True)
            .filter(
                Q(starts_at__isnull=True)
                | Q(starts_at__lte=at)
            )
            .filter(
                Q(ends_at__isnull=True)
                | Q(ends_at__gte=at)
            )
            .prefetch_related(
                "products",
                "categories",
                "brands",
                "countries",
            )
        )

        if country is None:
            queryset = queryset.filter(
                countries__isnull=True
            )
        else:
            queryset = queryset.filter(
                Q(countries__isnull=True)
                | Q(countries=country)
            ).distinct()

        return list(queryset)

    @classmethod
    def promotion_applies(
        cls,
        promotion,
        *,
        product,
        country=None,
        at=None,
    ):
        return (
            promotion.is_running(at=at)
            and applies_to_country(promotion, country)
            and targets_product(promotion, product)
        )

    @classmethod
    def best_promotion_for_amount(
        cls,
        *,
        product,
        amount,
        promotions=None,
        country=None,
        at=None,
    ):
        amount = money(amount)

        if promotions is None:
            promotions = cls.active_promotions(
                country=country,
                at=at,
            )

        best_promotion = None
        best_discount = Decimal("0.00")

        for promotion in promotions:
            if not cls.promotion_applies(
                promotion,
                product=product,
                country=country,
                at=at,
            ):
                continue

            discount = promotion.calculate_discount(amount)

            if discount > best_discount:
                best_promotion = promotion
                best_discount = discount

        return best_promotion, best_discount


class CouponService:
    @classmethod
    def find_by_code(cls, code):
        code = str(code or "").strip()

        if not code:
            return None

        return (
            Coupon.objects
            .filter(code__iexact=code)
            .first()
        )

    @classmethod
    def generate_code(cls, prefix="BOMBAA"):
        for _attempt in range(30):
            code = (
                f"{prefix}-{uuid4().hex[:8].upper()}"
            )

            if not Coupon.objects.filter(code=code).exists():
                return code

        raise RuntimeError(
            "Impossible de générer un code coupon unique."
        )

    @classmethod
    def current_uses(cls, coupon):
        return coupon.redemptions.filter(
            released_at__isnull=True
        ).count()

    @classmethod
    def validation_error(
        cls,
        coupon,
        *,
        subtotal,
        country=None,
        at=None,
        check_uses=True,
    ):
        if coupon is None:
            return None

        at = at or timezone.now()
        subtotal = money(subtotal)

        if not coupon.is_active:
            return "Ce coupon est désactivé."

        if coupon.value <= 0:
            return "Ce coupon n'a pas de réduction valide."

        if coupon.starts_at is not None and at < coupon.starts_at:
            return "Ce coupon n'est pas encore valide."

        if coupon.ends_at is not None and at > coupon.ends_at:
            return "Ce coupon a expiré."

        if not applies_to_country(coupon, country):
            return (
                "Ce coupon n'est pas disponible dans ce pays."
            )

        if subtotal < coupon.minimum_amount:
            return (
                "Le montant minimum pour utiliser ce coupon est "
                f"de {coupon.minimum_amount}."
            )

        if (
            check_uses
            and coupon.max_uses is not None
            and cls.current_uses(coupon) >= coupon.max_uses
        ):
            return (
                "Ce coupon a atteint sa limite d'utilisation."
            )

        return None

    @classmethod
    def eligible_amount(cls, coupon, priced_items):
        eligible = Decimal("0.00")

        for item in priced_items:
            if targets_product(
                coupon,
                item.variant.product,
            ):
                eligible += item.subtotal_after_promotion

        return money(eligible)

    @classmethod
    def release_for_order(cls, order, *, actor=None):
        redemption = (
            CouponRedemption.objects
            .select_related("coupon")
            .filter(
                order=order,
                released_at__isnull=True,
            )
            .first()
        )

        if redemption is None:
            return None

        # Sérialise la libération avec les créations de commandes
        # qui consomment le même coupon.
        Coupon.objects.select_for_update().filter(
            pk=redemption.coupon_id
        ).first()

        redemption.released_at = timezone.now()
        redemption.save(
            update_fields=["released_at"]
        )

        return redemption


@dataclass
class PricedItem:
    cart_item: object
    variant: object
    quantity: int
    unit_price: Decimal
    subtotal: Decimal
    promotion_discount: Decimal
    subtotal_after_promotion: Decimal
    promotion: object | None
    coupon_discount: Decimal = Decimal("0.00")

    @property
    def discounted_unit_price(self):
        if self.quantity <= 0:
            return money(self.unit_price)

        return money(
            self.subtotal_after_promotion / self.quantity
        )


@dataclass
class PricingResult:
    items: list[PricedItem] = field(default_factory=list)
    subtotal: Decimal = Decimal("0.00")
    promotion_discount: Decimal = Decimal("0.00")
    coupon_discount: Decimal = Decimal("0.00")
    discount_amount: Decimal = Decimal("0.00")
    total_amount: Decimal = Decimal("0.00")
    coupon: object | None = None
    coupon_error: str | None = None

    @property
    def applied_promotions(self):
        grouped = {}

        for item in self.items:
            if item.promotion is None:
                continue

            promotion = item.promotion
            entry = grouped.setdefault(
                promotion.id,
                {
                    "id": promotion.id,
                    "name": promotion.name,
                    "discount": Decimal("0.00"),
                },
            )
            entry["discount"] += item.promotion_discount

        return [
            {
                "id": entry["id"],
                "name": entry["name"],
                "discount": money(entry["discount"]),
            }
            for entry in grouped.values()
        ]


class PricingService:
    @classmethod
    def price_cart(
        cls,
        cart,
        *,
        country=None,
        coupon=None,
        strict_coupon=False,
        at=None,
    ):
        at = at or timezone.now()

        cart_items = list(
            cart.items
            .select_related("variant__product")
            .prefetch_related(
                "variant__product__product_categories"
            )
            .order_by("variant_id")
        )

        promotions = PromotionService.active_promotions(
            country=country,
            at=at,
        )

        priced_items = []
        subtotal = Decimal("0.00")
        promotion_discount = Decimal("0.00")

        for cart_item in cart_items:
            variant = cart_item.variant
            product = variant.product
            unit_price = money(variant.price)
            quantity = cart_item.quantity
            line_subtotal = money(unit_price * quantity)

            promotion, discount = (
                PromotionService.best_promotion_for_amount(
                    product=product,
                    amount=line_subtotal,
                    promotions=promotions,
                    country=country,
                    at=at,
                )
            )

            discount = min(discount, line_subtotal)
            line_after_promotion = money(
                line_subtotal - discount
            )

            priced_items.append(
                PricedItem(
                    cart_item=cart_item,
                    variant=variant,
                    quantity=quantity,
                    unit_price=unit_price,
                    subtotal=line_subtotal,
                    promotion_discount=discount,
                    subtotal_after_promotion=(
                        line_after_promotion
                    ),
                    promotion=promotion,
                )
            )

            subtotal += line_subtotal
            promotion_discount += discount

        subtotal = money(subtotal)
        promotion_discount = money(promotion_discount)

        coupon_discount = Decimal("0.00")
        coupon_error = None

        if coupon is not None:
            coupon_error = CouponService.validation_error(
                coupon,
                subtotal=subtotal,
                country=country,
                at=at,
            )

            if coupon_error is None:
                eligible_amount = (
                    CouponService.eligible_amount(
                        coupon,
                        priced_items,
                    )
                )

                if eligible_amount <= 0:
                    coupon_error = (
                        "Ce coupon ne s'applique à aucun "
                        "article du panier."
                    )
                else:
                    coupon_discount = (
                        coupon.calculate_discount(
                            eligible_amount
                        )
                    )

                    coupon_discount = min(
                        coupon_discount,
                        eligible_amount,
                        money(
                            subtotal - promotion_discount
                        ),
                    )

            if coupon_error is not None:
                coupon_discount = Decimal("0.00")

                if strict_coupon:
                    raise ValueError(coupon_error)

        discount_amount = money(
            promotion_discount + coupon_discount
        )

        total_amount = money(
            subtotal - discount_amount
        )

        if total_amount < 0:
            total_amount = Decimal("0.00")

        return PricingResult(
            items=priced_items,
            subtotal=subtotal,
            promotion_discount=promotion_discount,
            coupon_discount=money(coupon_discount),
            discount_amount=discount_amount,
            total_amount=total_amount,
            coupon=coupon,
            coupon_error=coupon_error,
        )

    @classmethod
    def price_items(
        cls,
        items,
        *,
        country=None,
        coupon=None,
        strict_coupon=False,
        at=None,
    ):
        """
        Variante utilitaire pour des articles déjà chargés.

        Elle conserve la même logique que `price_cart` et sert
        notamment aux intégrations qui ne possèdent pas de panier
        persistant.
        """

        if not items:
            result = PricingResult(coupon=coupon)

            if coupon is not None:
                result.coupon_error = (
                    "Votre panier est vide."
                )

                if strict_coupon:
                    raise ValueError(result.coupon_error)

            return result

        first_item = items[0]

        if hasattr(first_item, "cart"):
            return cls.price_cart(
                first_item.cart,
                country=country,
                coupon=coupon,
                strict_coupon=strict_coupon,
                at=at,
            )

        raise ValueError(
            "Articles de panier non pris en charge."
        )
