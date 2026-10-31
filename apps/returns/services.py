from decimal import Decimal, ROUND_HALF_UP

from django.db import transaction
from django.db.models import Sum
from django.utils import timezone

from apps.accounts.permissions import user_has_permission
from apps.notifications.models import Notification
from apps.notifications.services import NotificationService
from apps.orders.models import Order
from apps.payments.models import Payment
from apps.stocks.models import Stock, StockMovement

from .models import Refund, ReturnItem, ReturnRequest


MONEY = Decimal("0.01")


class ReturnService:
    """
    Règles métier des demandes de retour BOMBAA.
    """

    RETURNABLE_ORDER_STATUSES = [
        Order.Status.DELIVERED,
        Order.Status.COMPLETED,
        Order.Status.RETURNED,
    ]

    ACTIVE_RETURN_STATUSES = [
        ReturnRequest.Status.REQUESTED,
        ReturnRequest.Status.APPROVED,
        ReturnRequest.Status.RECEIVED,
        ReturnRequest.Status.REFUNDED,
    ]

    @staticmethod
    def is_manager(user):
        if not user or not user.is_authenticated:
            return False

        return (
            user.is_staff
            or user.is_superuser
            or user_has_permission(user, "returns.update")
        )

    @staticmethod
    def money(value):
        return Decimal(value or 0).quantize(
            MONEY,
            rounding=ROUND_HALF_UP,
        )

    @classmethod
    def active_quantities(cls, order):
        rows = (
            ReturnItem.objects
            .filter(
                return_request__order=order,
                return_request__status__in=(
                    cls.ACTIVE_RETURN_STATUSES
                ),
            )
            .values("order_item_id")
            .annotate(total=Sum("quantity"))
        )

        return {
            row["order_item_id"]: row["total"]
            for row in rows
        }

    @classmethod
    def available_items(cls, order):
        returned = cls.active_quantities(order)
        available = []

        for item in (
            order.items
            .select_related("variant")
            .order_by("id")
        ):
            returned_quantity = returned.get(item.id, 0)
            available_quantity = (
                item.quantity - returned_quantity
            )

            if available_quantity <= 0:
                continue

            available.append({
                "order_item": item.id,
                "product_name": item.product_name,
                "sku": item.sku,
                "ordered_quantity": item.quantity,
                "returned_quantity": returned_quantity,
                "available_quantity": available_quantity,
                "unit_price": str(item.unit_price),
            })

        return available

    @staticmethod
    def calculate_line_amount(order_item, quantity):
        net_total = (
            order_item.subtotal
            - order_item.discount_amount
        )

        if order_item.quantity <= 0:
            return Decimal("0.00")

        return ReturnService.money(
            net_total * quantity / order_item.quantity
        )

    @classmethod
    def validate_order(cls, order):
        if order is None:
            raise ValueError("La commande est obligatoire.")

        if order.status not in cls.RETURNABLE_ORDER_STATUSES:
            raise ValueError(
                "Une demande de retour n'est possible que pour "
                "une commande livrée, terminée ou déjà "
                "partiellement retournée."
            )

        if not order.items.exists():
            raise ValueError(
                "Cette commande ne contient aucun article."
            )

    @classmethod
    @transaction.atomic
    def create_return(cls, *, order, items, reason, actor):
        order = (
            Order.objects
            .select_for_update()
            .get(pk=order.pk)
        )

        cls.validate_order(order)

        reason = (reason or "").strip()

        if not reason:
            raise ValueError(
                "Le motif du retour est obligatoire."
            )

        if not items:
            raise ValueError(
                "Sélectionnez au moins un article à retourner."
            )

        returned = cls.active_quantities(order)
        prepared_items = []
        total_amount = Decimal("0.00")
        seen_items = set()

        for entry in items:
            order_item = entry["order_item"]
            quantity = entry["quantity"]

            if order_item.id in seen_items:
                raise ValueError(
                    "Un article ne peut apparaître qu'une seule "
                    "fois dans la demande."
                )

            seen_items.add(order_item.id)

            if order_item.order_id != order.id:
                raise ValueError(
                    "Un des articles n'appartient pas à cette "
                    "commande."
                )

            if quantity <= 0:
                raise ValueError(
                    "La quantité retournée doit être supérieure "
                    "à zéro."
                )

            available_quantity = (
                order_item.quantity
                - returned.get(order_item.id, 0)
            )

            if quantity > available_quantity:
                raise ValueError(
                    f"La quantité retournée pour {order_item.sku} "
                    f"dépasse la quantité disponible "
                    f"({available_quantity})."
                )

            line_amount = cls.calculate_line_amount(
                order_item,
                quantity,
            )
            unit_price = cls.money(
                line_amount / quantity
            )
            total_amount += line_amount

            prepared_items.append(
                ReturnItem(
                    order_item=order_item,
                    product_name=order_item.product_name,
                    sku=order_item.sku,
                    quantity=quantity,
                    unit_price=unit_price,
                    subtotal=line_amount,
                )
            )

        return_request = ReturnRequest.objects.create(
            order=order,
            reason=reason,
            total_amount=cls.money(total_amount),
            currency=order.currency,
        )

        for item in prepared_items:
            item.return_request = return_request

        ReturnItem.objects.bulk_create(prepared_items)

        return return_request

    @classmethod
    def cancel(cls, *, return_request, actor):
        if return_request.status != ReturnRequest.Status.REQUESTED:
            raise ValueError(
                "Seule une demande en attente peut être annulée."
            )

        return_request.status = ReturnRequest.Status.CANCELLED
        return_request.cancelled_at = timezone.now()
        return_request.processed_by = actor
        return_request.save(
            update_fields=[
                "status",
                "cancelled_at",
                "processed_by",
                "updated_at",
            ]
        )

        return return_request

    @classmethod
    def approve(cls, *, return_request, actor):
        if return_request.status != ReturnRequest.Status.REQUESTED:
            raise ValueError(
                "Seule une demande en attente peut être approuvée."
            )

        return_request.status = ReturnRequest.Status.APPROVED
        return_request.approved_at = timezone.now()
        return_request.processed_by = actor
        return_request.save(
            update_fields=[
                "status",
                "approved_at",
                "processed_by",
                "updated_at",
            ]
        )

        return return_request

    @classmethod
    def reject(cls, *, return_request, actor, note=None):
        if return_request.status not in [
            ReturnRequest.Status.REQUESTED,
            ReturnRequest.Status.APPROVED,
        ]:
            raise ValueError(
                "Cette demande ne peut plus être rejetée."
            )

        return_request.status = ReturnRequest.Status.REJECTED
        return_request.rejected_at = timezone.now()
        return_request.admin_note = note
        return_request.processed_by = actor
        return_request.save(
            update_fields=[
                "status",
                "rejected_at",
                "admin_note",
                "processed_by",
                "updated_at",
            ]
        )

        return return_request

    @classmethod
    @transaction.atomic
    def receive(cls, *, return_request, actor):
        return_request = (
            ReturnRequest.objects
            .select_for_update()
            .get(pk=return_request.pk)
        )

        if return_request.status != ReturnRequest.Status.APPROVED:
            raise ValueError(
                "Seule une demande approuvée peut être réceptionnée."
            )

        items = list(
            return_request.items
            .select_related("order_item__variant")
            .order_by("id")
        )

        variant_ids = [
            item.order_item.variant_id
            for item in items
            if item.order_item.variant_id is not None
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
            variant_id = item.order_item.variant_id

            if variant_id is None:
                continue

            stock = stocks.get(variant_id)

            if stock is None:
                raise ValueError(
                    f"Aucun stock n'est configuré pour "
                    f"{item.sku}. Réception impossible."
                )

            stock.quantity += item.quantity
            stock.save(update_fields=["quantity", "updated_at"])

            StockMovement.objects.create(
                stock=stock,
                movement_type=StockMovement.MOVEMENT_IN,
                quantity=item.quantity,
                reason=(
                    f"Retour {return_request.reference}"
                ),
            )

        return_request.status = ReturnRequest.Status.RECEIVED
        return_request.received_at = timezone.now()
        return_request.processed_by = actor
        return_request.save(
            update_fields=[
                "status",
                "received_at",
                "processed_by",
                "updated_at",
            ]
        )

        order = return_request.order

        if order.status != Order.Status.REFUNDED:
            order.status = Order.Status.RETURNED
            order.save(
                update_fields=["status", "updated_at"]
            )

        return return_request

    @classmethod
    def mark_refunded(cls, *, return_request):
        processed = (
            return_request.refunds
            .filter(status=Refund.Status.PROCESSED)
            .aggregate(total=Sum("amount"))
        )["total"] or Decimal("0.00")

        if processed < return_request.total_amount:
            return False

        return_request.status = ReturnRequest.Status.REFUNDED
        return_request.refunded_at = timezone.now()
        return_request.save(
            update_fields=[
                "status",
                "refunded_at",
                "updated_at",
            ]
        )

        return True


class RefundService:
    """
    Règles métier des remboursements BOMBAA.
    """

    ACTIVE_STATUSES = [
        Refund.Status.PENDING,
        Refund.Status.APPROVED,
        Refund.Status.PROCESSED,
    ]

    @staticmethod
    def is_manager(user):
        if not user or not user.is_authenticated:
            return False

        return (
            user.is_staff
            or user.is_superuser
            or user_has_permission(user, "refunds.update")
        )

    @staticmethod
    def money(value):
        return Decimal(value or 0).quantize(
            MONEY,
            rounding=ROUND_HALF_UP,
        )

    @classmethod
    def reserved_amount(
        cls,
        *,
        order,
        return_request=None,
        payment=None,
        statuses=None,
    ):
        queryset = Refund.objects.filter(
            order=order,
            status__in=statuses or cls.ACTIVE_STATUSES,
        )

        if return_request is not None:
            queryset = queryset.filter(
                return_request=return_request
            )

        if payment is not None:
            queryset = queryset.filter(payment=payment)

        return (
            queryset.aggregate(total=Sum("amount"))["total"]
            or Decimal("0.00")
        )

    @classmethod
    def available_order_amount(cls, order):
        return max(
            order.total_amount
            - cls.reserved_amount(order=order),
            Decimal("0.00"),
        )

    @classmethod
    def available_return_amount(cls, return_request):
        return max(
            return_request.total_amount
            - cls.reserved_amount(
                order=return_request.order,
                return_request=return_request,
            ),
            Decimal("0.00"),
        )

    @classmethod
    @transaction.atomic
    def create_refund(
        cls,
        *,
        order,
        actor,
        reason,
        method=Refund.Method.ORIGINAL_PAYMENT,
        amount=None,
        payment=None,
        return_request=None,
        notes=None,
        external_reference=None,
    ):
        order = (
            Order.objects
            .select_for_update()
            .get(pk=order.pk)
        )

        if order.status == Order.Status.CANCELLED:
            raise ValueError(
                "Impossible de rembourser une commande annulée."
            )

        reason = (reason or "").strip()

        if not reason:
            raise ValueError(
                "Le motif du remboursement est obligatoire."
            )

        if return_request is not None:
            if return_request.order_id != order.id:
                raise ValueError(
                    "La demande de retour ne correspond pas à "
                    "cette commande."
                )

            if return_request.status != ReturnRequest.Status.RECEIVED:
                raise ValueError(
                    "Le retour doit être réceptionné avant tout "
                    "remboursement."
                )

            available = cls.available_return_amount(
                return_request
            )
        else:
            available = cls.available_order_amount(order)

        if amount is None:
            amount = available

        amount = cls.money(amount)

        if amount <= 0:
            raise ValueError(
                "Le montant du remboursement doit être "
                "supérieur à zéro."
            )

        if amount > available:
            raise ValueError(
                f"Le montant demandé dépasse le montant "
                f"remboursable ({available})."
            )

        if payment is not None:
            if payment.order_id != order.id:
                raise ValueError(
                    "Le paiement ne correspond pas à cette "
                    "commande."
                )

            if payment.status != Payment.Status.SUCCESS:
                raise ValueError(
                    "Seul un paiement réussi peut être remboursé."
                )

            payment_available = max(
                payment.amount
                - cls.reserved_amount(
                    order=order,
                    payment=payment,
                ),
                Decimal("0.00"),
            )

            if amount > payment_available:
                raise ValueError(
                    "Le montant dépasse le solde remboursable "
                    "de ce paiement."
                )

        return Refund.objects.create(
            order=order,
            return_request=return_request,
            payment=payment,
            amount=amount,
            currency=order.currency,
            reason=reason,
            method=method,
            notes=notes,
            external_reference=external_reference,
            requested_by=actor,
        )

    @classmethod
    def approve(cls, *, refund, actor):
        if refund.status == Refund.Status.APPROVED:
            return refund

        if refund.status != Refund.Status.PENDING:
            raise ValueError(
                "Seul un remboursement en attente peut être "
                "approuvé."
            )

        refund.status = Refund.Status.APPROVED
        refund.approved_at = timezone.now()
        refund.processed_by = actor
        refund.save(
            update_fields=[
                "status",
                "approved_at",
                "processed_by",
                "updated_at",
            ]
        )

        return refund

    @classmethod
    def reject(cls, *, refund, actor, note=None):
        if refund.status not in [
            Refund.Status.PENDING,
            Refund.Status.APPROVED,
        ]:
            raise ValueError(
                "Ce remboursement ne peut plus être rejeté."
            )

        refund.status = Refund.Status.REJECTED
        refund.rejected_at = timezone.now()
        refund.notes = note or refund.notes
        refund.processed_by = actor
        refund.save(
            update_fields=[
                "status",
                "rejected_at",
                "notes",
                "processed_by",
                "updated_at",
            ]
        )

        return refund

    @classmethod
    @transaction.atomic
    def process(
        cls,
        *,
        refund,
        actor,
        external_reference=None,
        notes=None,
    ):
        refund = (
            Refund.objects
            .select_for_update()
            .get(pk=refund.pk)
        )

        if refund.status not in [
            Refund.Status.PENDING,
            Refund.Status.APPROVED,
        ]:
            raise ValueError(
                "Ce remboursement ne peut plus être traité."
            )

        refund.status = Refund.Status.PROCESSED
        refund.processed_at = timezone.now()
        refund.processed_by = actor
        refund.external_reference = (
            external_reference or refund.external_reference
        )
        refund.notes = notes or refund.notes
        refund.save(
            update_fields=[
                "status",
                "processed_at",
                "processed_by",
                "external_reference",
                "notes",
                "updated_at",
            ]
        )

        if refund.payment is not None:
            payment_processed = cls.reserved_amount(
                order=refund.order,
                payment=refund.payment,
                statuses=[Refund.Status.PROCESSED],
            )

            if payment_processed >= refund.payment.amount:
                refund.payment.status = (
                    Payment.Status.REFUNDED
                )
                refund.payment.save(
                    update_fields=["status", "updated_at"]
                )

        if refund.return_request is not None:
            ReturnService.mark_refunded(
                return_request=refund.return_request
            )

        cls._refresh_order_status(refund.order)
        cls._notify_refund(refund)

        return refund

    @classmethod
    def _refresh_order_status(cls, order):
        processed = cls.reserved_amount(
            order=order,
            statuses=[Refund.Status.PROCESSED],
        )

        if (
            processed >= order.total_amount
            and order.status != Order.Status.CANCELLED
        ):
            order.status = Order.Status.REFUNDED
            order.save(
                update_fields=["status", "updated_at"]
            )

    @staticmethod
    def _notify_refund(refund):
        if refund.payment is not None:
            NotificationService.refund_processed(
                refund.payment,
                amount=refund.amount,
            )
            return

        order = refund.order

        NotificationService.notify(
            user=order.user,
            event=Notification.Event.REFUND,
            title="Remboursement",
            message=(
                f"Le remboursement de {refund.amount} "
                f"{refund.currency} pour la commande "
                f"{order.reference} a été traité."
            ),
            order=order,
            data={
                "refund_id": refund.id,
                "refund_reference": refund.reference,
                "order_id": order.id,
                "amount": str(refund.amount),
                "currency": refund.currency,
            },
        )
