from decimal import Decimal
from uuid import uuid4

from django.db import transaction
from django.utils import timezone

from apps.orders.models import Order

from .models import Payment, PaymentMethod, Transaction


class PaymentService:

    @staticmethod
    def generate_payment_reference():
        return f"PAY-{uuid4().hex[:12].upper()}"

    @staticmethod
    def generate_transaction_reference():
        return f"TXN-{uuid4().hex[:12].upper()}"

    @classmethod
    @transaction.atomic
    def create_payment(
        cls,
        *,
        order,
        payment_method,
    ):
        """
        Crée un paiement et sa première transaction.

        Aucun appel à un prestataire externe n'est effectué ici.
        """

        # --------------------------------------------------
        # 1. Vérifier la commande
        # --------------------------------------------------

        if not order:
            raise ValueError(
                "La commande est obligatoire."
            )

        if order.status in [
            Order.Status.CANCELLED,
        ]:
            raise ValueError(
                "Impossible de payer une commande annulée."
            )

        # --------------------------------------------------
        # 2. Vérifier le moyen de paiement
        # --------------------------------------------------

        if not payment_method:
            raise ValueError(
                "Le moyen de paiement est obligatoire."
            )

        if not payment_method.is_active:
            raise ValueError(
                "Ce moyen de paiement est actuellement désactivé."
            )

        # --------------------------------------------------
        # 3. Vérifier qu'il n'existe pas déjà
        #    un paiement en cours
        # --------------------------------------------------

        existing_payment = (
            Payment.objects
            .filter(
                order=order,
                status__in=[
                    Payment.Status.PENDING,
                    Payment.Status.PROCESSING,
                ],
            )
            .first()
        )

        if existing_payment:
            raise ValueError(
                "Cette commande possède déjà "
                "un paiement en cours."
            )

        # --------------------------------------------------
        # 4. Vérifier le montant
        # --------------------------------------------------

        amount = Decimal(order.total_amount)

        if amount <= 0:
            raise ValueError(
                "Le montant de la commande doit être supérieur à 0."
            )

        # --------------------------------------------------
        # 5. Créer le paiement
        # --------------------------------------------------

        payment = Payment.objects.create(
            order=order,
            payment_method=payment_method,
            reference=cls.generate_payment_reference(),
            amount=amount,
            currency=order.currency,
            status=Payment.Status.PENDING,
        )

        # --------------------------------------------------
        # 6. Créer la première transaction
        # --------------------------------------------------

        Transaction.objects.create(
            payment=payment,
            reference=cls.generate_transaction_reference(),
            amount=amount,
            currency=order.currency,
            status=Transaction.Status.PENDING,
        )

        return payment

    @classmethod
    @transaction.atomic
    def mark_payment_processing(
        cls,
        *,
        payment,
    ):
        if payment.status != Payment.Status.PENDING:
            raise ValueError(
                "Seul un paiement en attente "
                "peut passer en traitement."
            )

        payment.status = Payment.Status.PROCESSING
        payment.save(
            update_fields=[
                "status",
                "updated_at",
            ]
        )

        payment.transactions.update(
            status=Transaction.Status.PENDING
        )

        return payment

    @classmethod
    @transaction.atomic
    def mark_payment_success(
        cls,
        *,
        payment,
        external_reference=None,
        response_message=None,
    ):
        if payment.status in [
            Payment.Status.SUCCESS,
            Payment.Status.REFUNDED,
        ]:
            return payment

        payment.status = Payment.Status.SUCCESS
        payment.paid_at = timezone.now()

        payment.save(
            update_fields=[
                "status",
                "paid_at",
                "updated_at",
            ]
        )

        transaction_obj = (
            payment.transactions
            .order_by("-created_at")
            .first()
        )

        if transaction_obj:
            transaction_obj.status = (
                Transaction.Status.SUCCESS
            )

            transaction_obj.external_reference = (
                external_reference
            )

            transaction_obj.response_message = (
                response_message
            )

            transaction_obj.transaction_date = (
                timezone.now()
            )

            transaction_obj.save(
                update_fields=[
                    "status",
                    "external_reference",
                    "response_message",
                    "transaction_date",
                ]
            )

        return payment

    @classmethod
    @transaction.atomic
    def mark_payment_failed(
        cls,
        *,
        payment,
        response_message=None,
    ):
        if payment.status in [
            Payment.Status.SUCCESS,
            Payment.Status.REFUNDED,
        ]:
            raise ValueError(
                "Un paiement déjà réussi "
                "ne peut pas être marqué comme échoué."
            )

        payment.status = Payment.Status.FAILED

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
            transaction_obj.status = (
                Transaction.Status.FAILED
            )

            transaction_obj.response_message = (
                response_message
            )

            transaction_obj.transaction_date = (
                timezone.now()
            )

            transaction_obj.save(
                update_fields=[
                    "status",
                    "response_message",
                    "transaction_date",
                ]
            )

        return payment