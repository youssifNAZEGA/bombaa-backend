from decimal import Decimal
from uuid import uuid4

from django.db import transaction
from django.utils import timezone

from rest_framework.exceptions import PermissionDenied

from apps.accounts.permissions import user_has_permission
from apps.audit.models import AuditLog
from apps.audit.services import AuditService
from apps.cart.models import Cart
from apps.notifications.services import NotificationService
from apps.payments.models import Payment, Transaction
from apps.promotions.models import Coupon, CouponRedemption
from apps.promotions.services import (
    CouponService,
    PricingService,
)
from apps.shipping.models import Delivery
from apps.shipping.services import ShippingService
from apps.stocks.models import Stock, StockMovement

from .models import Order, OrderAddress, OrderItem


class OrderService:
    """
    Règles métier des commandes BOMBAA.

    Tous les montants sont calculés côté serveur.
    Le client ne peut jamais imposer un sous-total, des frais
    de livraison ou une remise.
    """

    # Transitions autorisées en dehors de l'annulation.
    STATUS_TRANSITIONS = {
        Order.Status.PENDING: {
            Order.Status.CANCELLED,
        },
        Order.Status.CONFIRMED: {
            Order.Status.PROCESSING,
            Order.Status.CANCELLED,
        },
        Order.Status.PROCESSING: {
            Order.Status.SHIPPED,
            Order.Status.CANCELLED,
        },
        Order.Status.SHIPPED: {
            Order.Status.DELIVERED,
        },
        Order.Status.DELIVERED: {
            Order.Status.COMPLETED,
        },
        Order.Status.CANCELLED: set(),
        Order.Status.COMPLETED: set(),
        Order.Status.RETURNED: set(),
        Order.Status.REFUNDED: set(),
    }

    # Statuts depuis lesquels une annulation est possible.
    CANCELLABLE_STATUSES = {
        Order.Status.PENDING,
        Order.Status.CONFIRMED,
        Order.Status.PROCESSING,
    }

    @staticmethod
    def generate_reference():
        return f"CMD-{uuid4().hex[:12].upper()}"

    @classmethod
    @transaction.atomic
    def create_order(
        cls,
        *,
        user,
        address,
        shipping_method=None,
        notes=None,
        coupon_code=None,
    ):
        """
        Crée une commande à partir du panier de l'utilisateur,
        réserve le stock et vide le panier.

        Les promotions sont calculées automatiquement. Un coupon
        peut être appliqué depuis le panier ou fourni au checkout.
        Le client ne peut jamais imposer un montant de remise.
        """

        if address.user_id != user.id:
            raise PermissionDenied(
                "Cette adresse ne vous appartient pas."
            )

        cart = (
            Cart.objects
            .select_for_update()
            .filter(user=user)
            .first()
        )

        if not cart:
            raise ValueError("Votre panier est vide.")

        cart_items = list(
            cart.items
            .select_related("variant__product")
            .order_by("variant_id")
        )

        if not cart_items:
            raise ValueError("Votre panier est vide.")

        variant_ids = [
            cart_item.variant_id
            for cart_item in cart_items
        ]

        stocks = {
            stock.variant_id: stock
            for stock in (
                Stock.objects
                .select_for_update()
                .filter(variant_id__in=variant_ids)
                .order_by("variant_id")
            )
        }

        checked_items = []
        subtotal = Decimal("0.00")

        for cart_item in cart_items:
            variant = cart_item.variant

            if not variant.is_active or not variant.product.is_active:
                raise ValueError(
                    f"La variante {variant.sku} "
                    "n'est plus disponible."
                )

            stock = stocks.get(variant.id)

            if not stock:
                raise ValueError(
                    f"Aucun stock n'est configuré "
                    f"pour {variant.sku}."
                )

            available_quantity = (
                stock.quantity - stock.reserved_quantity
            )

            if cart_item.quantity > available_quantity:
                raise ValueError(
                    f"Stock insuffisant pour {variant.sku}. "
                    f"Disponible : {available_quantity}."
                )

            item_subtotal = (
                variant.price * cart_item.quantity
            )

            subtotal += item_subtotal

            checked_items.append(
                {
                    "cart_item": cart_item,
                    "variant": variant,
                    "stock": stock,
                    "subtotal": item_subtotal,
                }
            )

        total_weight_grams = sum(
            (
                (item_data["variant"].product.weight_grams or 0)
                * item_data["cart_item"].quantity
            )
            for item_data in checked_items
        )

        country = ShippingService.resolve_country(address)

        if shipping_method is not None and country is None:
            raise ValueError(
                "Aucun pays de livraison n'est associé "
                "à cette adresse."
            )

        coupon = None
        normalized_coupon_code = str(
            coupon_code or ""
        ).strip()

        if normalized_coupon_code:
            coupon = (
                Coupon.objects
                .select_for_update()
                .filter(
                    code__iexact=normalized_coupon_code
                )
                .first()
            )

            if coupon is None:
                raise ValueError("Code coupon invalide.")

        elif cart.coupon_id is not None:
            coupon = (
                Coupon.objects
                .select_for_update()
                .filter(pk=cart.coupon_id)
                .first()
            )

        pricing = PricingService.price_cart(
            cart,
            country=country,
            coupon=coupon,
            strict_coupon=True,
        )

        subtotal = pricing.subtotal
        promotion_discount = pricing.promotion_discount
        coupon_discount = pricing.coupon_discount
        discount_amount = pricing.discount_amount

        shipping_quote = ShippingService.quote(
            country=country,
            method=shipping_method,
            weight_grams=total_weight_grams,
        )

        shipping_cost = shipping_quote.cost

        total_amount = pricing.total_amount + shipping_cost

        if total_amount < 0:
            total_amount = Decimal("0.00")

        order_currency = (
            shipping_quote.currency.code
            if shipping_quote.currency is not None
            else "XOF"
        )

        discount_details = {
            "promotions": [
                {
                    "id": promotion["id"],
                    "name": promotion["name"],
                    "discount": str(promotion["discount"]),
                }
                for promotion in pricing.applied_promotions
            ],
            "coupon": (
                {
                    "id": coupon.id,
                    "code": coupon.code,
                    "discount": str(coupon_discount),
                }
                if coupon is not None
                else None
            ),
        }

        order = Order.objects.create(
            user=user,
            reference=cls.generate_reference(),
            status=Order.Status.PENDING,
            subtotal=subtotal,
            shipping_cost=shipping_cost,
            shipping_weight_grams=total_weight_grams,
            promotion_discount=promotion_discount,
            coupon_discount=coupon_discount,
            coupon_code=coupon.code if coupon is not None else "",
            discount_details=discount_details,
            discount_amount=discount_amount,
            total_amount=total_amount,
            currency=order_currency,
            notes=notes,
        )

        OrderAddress.objects.create(
            order=order,
            recipient_name=(
                f"{address.first_name} "
                f"{address.last_name}"
            ),
            phone=address.phone,
            address_line1=address.address_line_1,
            address_line2=address.address_line_2,
            city=address.city,
            state=address.state,
            postal_code=address.postal_code,
            country_name=(
                country.name if country else address.country
            ),
            country_code=country.code if country else "",
        )

        if shipping_quote.method is not None:
            Delivery.objects.create(
                order=order,
                shipping_method=shipping_quote.method,
                estimated_delivery_date=(
                    ShippingService.estimated_delivery_date(
                        shipping_quote.method
                    )
                ),
            )

        priced_items = {
            item.cart_item.id: item
            for item in pricing.items
        }

        for item_data in checked_items:
            cart_item = item_data["cart_item"]
            variant = item_data["variant"]
            stock = item_data["stock"]
            priced_item = priced_items.get(cart_item.id)

            OrderItem.objects.create(
                order=order,
                variant=variant,
                product_name=variant.product.name,
                variant_description=variant.sku,
                sku=variant.sku,
                quantity=cart_item.quantity,
                unit_price=variant.price,
                subtotal=item_data["subtotal"],
                discount_amount=(
                    priced_item.promotion_discount
                    if priced_item is not None
                    else Decimal("0.00")
                ),
            )

            stock.reserved_quantity += (
                cart_item.quantity
            )

            stock.save(
                update_fields=[
                    "reserved_quantity",
                    "updated_at",
                ]
            )

        if coupon is not None:
            CouponRedemption.objects.create(
                coupon=coupon,
                user=user,
                order=order,
                discount_amount=coupon_discount,
            )

        cart.items.all().delete()

        if cart.coupon_id is not None:
            cart.coupon = None
            cart.save(
                update_fields=[
                    "coupon",
                    "updated_at",
                ]
            )

        NotificationService.order_created(order)

        return order

    @classmethod
    @transaction.atomic
    def cancel_order(
        cls,
        *,
        order,
        actor,
    ):
        """
        Annule une commande et remet le stock dans un état cohérent :

        - commande en attente : libère la réservation ;
        - commande confirmée ou en préparation : réintègre
          la quantité réellement déduite du stock.

        Un client ne peut annuler que sa propre commande
        en attente. Un administrateur peut annuler une commande
        en attente, confirmée ou en préparation.
        """

        order = (
            Order.objects
            .select_for_update()
            .get(pk=order.pk)
        )

        if order.status == Order.Status.CANCELLED:
            return order

        is_admin = (
            actor.is_staff
            or user_has_permission(actor, "orders.update")
        )

        if not is_admin and order.user_id != actor.id:
            raise PermissionDenied(
                "Cette commande ne vous appartient pas."
            )

        if not is_admin and order.status != Order.Status.PENDING:
            raise ValueError(
                "Vous ne pouvez annuler qu'une commande "
                "en attente de paiement."
            )

        if order.status not in cls.CANCELLABLE_STATUSES:
            raise ValueError(
                "La commande ne peut pas être annulée "
                f"depuis le statut {order.status}."
            )

        previous_status = order.status

        cls._cancel_active_payments(order)
        cls._restore_stock(order)

        order.status = Order.Status.CANCELLED
        order.save(
            update_fields=[
                "status",
                "updated_at",
            ]
        )

        CouponService.release_for_order(
            order,
            actor=actor,
        )

        NotificationService.order_cancelled(order)

        AuditService.log(
            action=AuditLog.Action.CANCEL,
            actor=actor,
            target=order,
            changes={
                "status": {
                    "before": previous_status,
                    "after": order.status,
                }
            },
            metadata={
                "reference": order.reference,
                "user_id": order.user_id,
            },
        )

        return order

    @classmethod
    @transaction.atomic
    def update_status(
        cls,
        *,
        order,
        new_status,
        actor,
    ):
        """
        Applique une transition de statut validée par un administrateur.
        """

        order = (
            Order.objects
            .select_for_update()
            .get(pk=order.pk)
        )

        if new_status == Order.Status.CANCELLED:
            return cls.cancel_order(
                order=order,
                actor=actor,
            )

        previous_status = order.status

        allowed_statuses = cls.STATUS_TRANSITIONS.get(
            order.status,
            set(),
        )

        if new_status not in allowed_statuses:
            raise ValueError(
                "Transition de statut impossible : "
                f"{order.status} -> {new_status}."
            )

        order.status = new_status
        order.save(
            update_fields=[
                "status",
                "updated_at",
            ]
        )

        NotificationService.order_status_changed(
            order,
            previous_status=previous_status,
        )

        AuditService.log(
            action=AuditLog.Action.STATUS_CHANGE,
            actor=actor,
            target=order,
            changes={
                "status": {
                    "before": previous_status,
                    "after": order.status,
                }
            },
            metadata={
                "reference": order.reference,
                "user_id": order.user_id,
            },
        )

        return order

    @staticmethod
    def _cancel_active_payments(order):
        """
        Annule les paiements encore en attente ou en traitement
        lorsque la commande est annulée.
        """

        pending_payments = (
            order.payments
            .select_for_update()
            .filter(
                status__in=[
                    Payment.Status.PENDING,
                    Payment.Status.PROCESSING,
                ]
            )
        )

        for payment in pending_payments:
            payment.status = Payment.Status.CANCELLED
            payment.save(
                update_fields=[
                    "status",
                    "updated_at",
                ]
            )

            transaction_obj = (
                payment.transactions
                .order_by("-created_at")
                .first()
            )

            if transaction_obj:
                transaction_obj.status = Transaction.Status.CANCELLED
                transaction_obj.response_message = (
                    "Commande annulée."
                )
                transaction_obj.transaction_date = timezone.now()
                transaction_obj.save(
                    update_fields=[
                        "status",
                        "response_message",
                        "transaction_date",
                    ]
                )

    @staticmethod
    def _restore_stock(order):
        """
        Libère la réservation (commande en attente) ou réintègre
        le stock (commande déjà payée) pour chaque article.
        """

        items = list(
            order.items
            .select_related("variant")
            .order_by("variant_id")
        )

        variant_ids = [
            item.variant_id
            for item in items
            if item.variant_id is not None
        ]

        stocks = {
            stock.variant_id: stock
            for stock in (
                Stock.objects
                .select_for_update()
                .filter(variant_id__in=variant_ids)
                .order_by("variant_id")
            )
        }

        for item in items:
            if item.variant_id is None:
                continue

            stock = stocks.get(item.variant_id)

            if not stock:
                raise ValueError(
                    f"Aucun stock n'est configuré pour "
                    f"{item.sku}. Annulation impossible."
                )

            if order.status == Order.Status.PENDING:
                if stock.reserved_quantity < item.quantity:
                    raise ValueError(
                        f"Réservation incohérente pour "
                        f"{item.sku}. Annulation impossible."
                    )

                stock.reserved_quantity -= item.quantity
                stock.save(
                    update_fields=[
                        "reserved_quantity",
                        "updated_at",
                    ]
                )

            else:
                stock.quantity += item.quantity
                stock.save(
                    update_fields=[
                        "quantity",
                        "updated_at",
                    ]
                )

                StockMovement.objects.create(
                    stock=stock,
                    movement_type=StockMovement.MOVEMENT_IN,
                    quantity=item.quantity,
                    reason=(
                        f"Annulation commande "
                        f"{order.reference}"
                    ),
                )
