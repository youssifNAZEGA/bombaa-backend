from django.db.models import Avg, Count

from apps.accounts.permissions import user_has_permission
from apps.orders.models import Order, OrderItem

from .models import Review


class ReviewService:
    """
    Règles métier des avis BOMBAA.

    Un avis est dit vérifié lorsqu'il existe une commande non
    annulée contenant le produit acheté par l'utilisateur.
    """

    ELIGIBLE_ORDER_STATUSES = [
        Order.Status.PENDING,
        Order.Status.CONFIRMED,
        Order.Status.PROCESSING,
        Order.Status.SHIPPED,
        Order.Status.DELIVERED,
        Order.Status.COMPLETED,
    ]

    @staticmethod
    def is_moderator(user):
        if not user or not user.is_authenticated:
            return False

        return (
            user.is_staff
            or user.is_superuser
            or user_has_permission(user, "reviews.moderate")
        )

    @classmethod
    def purchase_order_item(cls, user, product):
        if not user or not user.is_authenticated:
            return None

        return (
            OrderItem.objects
            .filter(
                order__user=user,
                order__status__in=cls.ELIGIBLE_ORDER_STATUSES,
                variant__product=product,
            )
            .select_related("order")
            .order_by("-order__created_at", "-id")
            .first()
        )

    @classmethod
    def has_purchased(cls, user, product):
        return cls.purchase_order_item(user, product) is not None

    @staticmethod
    def approved_reviews():
        return Review.objects.filter(
            status=Review.Status.APPROVED
        )

    @staticmethod
    def stats_for_product(product):
        stats = Review.objects.filter(
            product=product,
            status=Review.Status.APPROVED,
        ).aggregate(
            average_rating=Avg("rating"),
            review_count=Count("id"),
        )

        return {
            "average_rating": stats["average_rating"],
            "review_count": stats["review_count"] or 0,
        }
