import logging
from decimal import Decimal

from apps.accounts.models import User

from .models import Notification, NotificationPreference


logger = logging.getLogger(__name__)


class NotificationService:
    """
    Point d'entrée unique pour créer les notifications BOMBAA.

    Les notifications in-app sont persistées en base. Les canaux
    externes (email, SMS, push) sont préparés et journalisés ; leur
    envoi effectif dépendra du fournisseur configuré en production.
    """

    @staticmethod
    def _format_money(amount, currency):
        if amount is None:
            amount = Decimal("0.00")

        return f"{amount} {currency}"

    @classmethod
    def get_preferences(cls, user):
        preferences, _created = (
            NotificationPreference.objects.get_or_create(
                user=user
            )
        )

        return preferences

    @classmethod
    def notify(
        cls,
        *,
        user,
        event,
        title,
        message,
        order=None,
        product=None,
        data=None,
        force_in_app=False,
    ):
        if user is None or not user.is_active:
            return None

        preferences = cls.get_preferences(user)

        if not preferences.in_app_enabled and not force_in_app:
            cls._dispatch_external(
                preferences=preferences,
                user=user,
                event=event,
                title=title,
                message=message,
            )

            return None

        notification = Notification.objects.create(
            user=user,
            event=event,
            channel=Notification.Channel.IN_APP,
            title=title,
            message=message,
            order=order,
            product=product,
            data=data or {},
        )

        cls._dispatch_external(
            preferences=preferences,
            user=user,
            event=event,
            title=title,
            message=message,
        )

        return notification

    @staticmethod
    def _dispatch_external(
        *,
        preferences,
        user,
        event,
        title,
        message,
    ):
        channels = []

        if preferences.email_enabled:
            channels.append(Notification.Channel.EMAIL)

        if preferences.sms_enabled:
            channels.append(Notification.Channel.SMS)

        if preferences.push_enabled:
            channels.append(Notification.Channel.PUSH)

        for channel in channels:
            logger.info(
                "notification.%s.queued user_id=%s event=%s title=%s",
                channel.lower(),
                user.id,
                event,
                title,
            )

    @classmethod
    def broadcast(
        cls,
        *,
        event,
        title,
        message,
        recipients=None,
        product=None,
        data=None,
        force_in_app=False,
    ):
        if recipients is None:
            recipients = User.objects.filter(
                is_active=True,
                is_staff=False,
                is_superuser=False,
            )

        created_count = 0

        for user in recipients:
            notification = cls.notify(
                user=user,
                event=event,
                title=title,
                message=message,
                product=product,
                data=data,
                force_in_app=force_in_app,
            )

            if notification is not None:
                created_count += 1

        return created_count

    # ------------------------------------------------------------------
    # Commandes
    # ------------------------------------------------------------------

    @classmethod
    def order_created(cls, order):
        return cls.notify(
            user=order.user,
            event=Notification.Event.ORDER_CREATED,
            title="Commande créée",
            message=(
                f"Votre commande {order.reference} a bien été "
                "créée. Vous pouvez maintenant procéder au paiement."
            ),
            order=order,
            data={
                "order_id": order.id,
                "reference": order.reference,
            },
        )

    @classmethod
    def order_confirmed(cls, order):
        return cls.notify(
            user=order.user,
            event=Notification.Event.ORDER_CONFIRMED,
            title="Commande confirmée",
            message=(
                f"Votre commande {order.reference} est confirmée. "
                "Nous préparons vos articles."
            ),
            order=order,
            data={
                "order_id": order.id,
                "reference": order.reference,
            },
        )

    @classmethod
    def order_processing(cls, order):
        return cls.notify(
            user=order.user,
            event=Notification.Event.ORDER_PROCESSING,
            title="Commande en préparation",
            message=(
                f"Votre commande {order.reference} est en cours "
                "de préparation."
            ),
            order=order,
            data={
                "order_id": order.id,
                "reference": order.reference,
            },
        )

    @classmethod
    def order_shipped(cls, order):
        return cls.notify(
            user=order.user,
            event=Notification.Event.ORDER_SHIPPED,
            title="Commande expédiée",
            message=(
                f"Votre commande {order.reference} a été expédiée."
            ),
            order=order,
            data={
                "order_id": order.id,
                "reference": order.reference,
            },
        )

    @classmethod
    def order_delivered(cls, order):
        return cls.notify(
            user=order.user,
            event=Notification.Event.ORDER_DELIVERED,
            title="Commande livrée",
            message=(
                f"Votre commande {order.reference} a été livrée. "
                "Merci pour votre confiance."
            ),
            order=order,
            data={
                "order_id": order.id,
                "reference": order.reference,
            },
        )

    @classmethod
    def order_cancelled(cls, order):
        return cls.notify(
            user=order.user,
            event=Notification.Event.ORDER_CANCELLED,
            title="Commande annulée",
            message=(
                f"Votre commande {order.reference} a été annulée."
            ),
            order=order,
            data={
                "order_id": order.id,
                "reference": order.reference,
            },
        )

    @classmethod
    def order_status_changed(cls, order, previous_status):
        if previous_status == order.status:
            return None

        handlers = {
            "CONFIRMED": cls.order_confirmed,
            "PROCESSING": cls.order_processing,
            "SHIPPED": cls.order_shipped,
            "DELIVERED": cls.order_delivered,
        }

        handler = handlers.get(order.status)

        if handler is None:
            return None

        return handler(order)

    # ------------------------------------------------------------------
    # Paiements
    # ------------------------------------------------------------------

    @classmethod
    def payment_succeeded(cls, payment):
        order = payment.order

        return cls.notify(
            user=order.user,
            event=Notification.Event.PAYMENT_CONFIRMED,
            title="Paiement confirmé",
            message=(
                f"Le paiement {payment.reference} de "
                f"{cls._format_money(payment.amount, payment.currency)} "
                "a été confirmé."
            ),
            order=order,
            data={
                "payment_id": payment.id,
                "payment_reference": payment.reference,
                "order_id": order.id,
                "amount": str(payment.amount),
                "currency": payment.currency,
            },
        )

    @classmethod
    def payment_failed(cls, payment):
        order = payment.order

        return cls.notify(
            user=order.user,
            event=Notification.Event.PAYMENT_FAILED,
            title="Paiement échoué",
            message=(
                f"Le paiement {payment.reference} de "
                f"{cls._format_money(payment.amount, payment.currency)} "
                "n'a pas abouti. Vous pouvez réessayer."
            ),
            order=order,
            data={
                "payment_id": payment.id,
                "payment_reference": payment.reference,
                "order_id": order.id,
                "amount": str(payment.amount),
                "currency": payment.currency,
            },
        )

    @classmethod
    def refund_processed(cls, payment, amount=None):
        order = payment.order
        refund_amount = amount if amount is not None else payment.amount

        return cls.notify(
            user=order.user,
            event=Notification.Event.REFUND,
            title="Remboursement",
            message=(
                f"Le remboursement de "
                f"{cls._format_money(refund_amount, payment.currency)} "
                f"pour le paiement {payment.reference} a été traité."
            ),
            order=order,
            data={
                "payment_id": payment.id,
                "payment_reference": payment.reference,
                "order_id": order.id,
                "amount": str(refund_amount),
                "currency": payment.currency,
            },
        )

    # ------------------------------------------------------------------
    # Livraison
    # ------------------------------------------------------------------

    @classmethod
    def delivery_status_changed(cls, delivery, previous_status=None):
        if previous_status == delivery.status:
            return None

        order = delivery.order

        if order.status == "CANCELLED":
            return None

        if delivery.status == "PREPARING":
            return cls.order_processing(order)

        if delivery.status in ["SHIPPED", "IN_TRANSIT"]:
            return cls.order_shipped(order)

        if delivery.status == "DELIVERED":
            return cls.order_delivered(order)

        return None

    # ------------------------------------------------------------------
    # Catalogue et marketing
    # ------------------------------------------------------------------

    @classmethod
    def new_product(cls, product):
        if not product.is_active:
            return 0

        return cls.broadcast(
            event=Notification.Event.NEW_PRODUCT,
            title="Nouveau produit",
            message=(
                f"Découvrez notre nouveau produit : {product.name}."
            ),
            product=product,
            data={
                "product_id": product.id,
                "slug": product.slug,
            },
        )

    @classmethod
    def promotion(
        cls,
        *,
        product=None,
        title="Promotion",
        message=None,
        recipients=None,
        data=None,
    ):
        if message is None:
            message = (
                f"Profitez de notre promotion sur {product.name}."
                if product is not None
                else "Profitez de notre nouvelle promotion."
            )

        payload = (
            {"product_id": product.id}
            if product is not None
            else {}
        )
        payload.update(data or {})

        return cls.broadcast(
            event=Notification.Event.PROMOTION,
            title=title,
            message=message,
            recipients=recipients,
            product=product,
            data=payload,
        )

    @classmethod
    def new_coupon(
        cls,
        *,
        title="Nouveau coupon",
        message="Un nouveau coupon est disponible.",
        recipients=None,
        data=None,
    ):
        return cls.broadcast(
            event=Notification.Event.NEW_COUPON,
            title=title,
            message=message,
            recipients=recipients,
            data=data or {},
        )

    @classmethod
    def back_in_stock(cls, variant):
        from apps.wishlist.models import WishlistItem

        product = variant.product

        recipients = [
            item.wishlist.user
            for item in (
                WishlistItem.objects
                .filter(
                    variant=variant,
                    wishlist__user__is_active=True,
                )
                .select_related("wishlist__user")
            )
        ]

        created_count = 0

        for user in recipients:
            notification = cls.notify(
                user=user,
                event=Notification.Event.BACK_IN_STOCK,
                title=f"Retour en stock : {product.name}",
                message=(
                    f"Le produit {product.name} ({variant.sku}) "
                    "est de nouveau disponible."
                ),
                product=product,
                data={
                    "product_id": product.id,
                    "variant_id": variant.id,
                    "sku": variant.sku,
                },
            )

            if notification is not None:
                created_count += 1

        return created_count
