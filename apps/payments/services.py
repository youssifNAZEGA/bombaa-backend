from decimal import Decimal
from uuid import uuid4

from django.core.exceptions import ObjectDoesNotExist
from django.db import transaction
from django.utils import timezone

from apps.geography.models import Country
from apps.notifications.services import NotificationService
from apps.orders.models import Order

from .models import Payment, PaymentMethod, Transaction
from apps.payments.providers.paydunya import PayDunyaProvider
from apps.stocks.models import Stock, StockMovement

class PaymentService:

    @staticmethod
    def start_paydunya_payment(payment):
        """
        Crée une Checkout Invoice PayDunya pour un Payment BOMBAA.
        """

        if payment.status not in [
            Payment.Status.PENDING,
            Payment.Status.PROCESSING,
        ]:
            raise ValueError(
                f"Le paiement {payment.reference} "
                f"ne peut pas être envoyé à PayDunya "
                f"avec le statut {payment.status}."
            )

        order = payment.order
        user = order.user

        customer = {
            "name": (
                f"{user.first_name} {user.last_name}"
            ).strip(),
            "email": user.email,
            "phone": user.phone or "",
        }

        provider = PayDunyaProvider()

        result = provider.create_payment(
            payment=payment,
            customer=customer,
        )

        token = result["token"]

        transaction = (
            payment.transactions
            .order_by("-created_at")
            .first()
        )

        if not transaction:
            raise ValueError(
                "Aucune transaction trouvée "
                f"pour le paiement {payment.reference}."
            )

        transaction.external_reference = token
        transaction.response_message = (
            "Checkout Invoice PayDunya créée."
        )
        transaction.save(
            update_fields=[
                "external_reference",
                "response_message",
            ]
        )

        if payment.status == Payment.Status.PENDING:
            PaymentService.mark_payment_processing(payment=payment)

        return result

    
    @staticmethod
    def check_paydunya_payment(payment):
        provider = PayDunyaProvider()
        result = provider.check_payment(payment=payment)

        response_code = str(result.get("response_code", ""))
        invoice = result.get("invoice") or {}
        provider_status = str(invoice.get("status", "")).lower()

        if response_code != "00":
            raise ValueError(
                result.get(
                    "response_text",
                    "Impossible de vérifier le paiement PayDunya.",
                )
            )

        if provider_status == "completed":
            PaymentService.mark_payment_success(
                payment=payment,
                external_reference=invoice.get("token"),
                response_message="Paiement confirmé par PayDunya.",
            )

        elif provider_status == "failed":
            PaymentService.mark_payment_failed(
                payment=payment,
                response_message="Paiement refusé par PayDunya.",
            )

        
        elif provider_status == "cancelled":
            PaymentService.mark_payment_cancelled(
                payment=payment,
                response_message="Paiement annulé par PayDunya.",
            )
        
        elif provider_status in ["pending", "processing"]:
            if payment.status == Payment.Status.PENDING:
                PaymentService.mark_payment_processing(
                    payment=payment
                )

        else:
            raise ValueError(
                f"Statut PayDunya non reconnu : {provider_status!r}"
            )

        payment.refresh_from_db()
        return {
            "payment": payment,
            "paydunya": result,
        }
    
    @classmethod
    def _finalize_order_stock(cls, order):
        """
        Décrémente le stock et libère la réservation
        lorsque le paiement est confirmé.
        L'appelant doit verrouiller la commande.
        """
        if order.status != Order.Status.PENDING:
            if order.status == Order.Status.CONFIRMED:
                return
            raise ValueError(
                "La commande ne peut pas être confirmée "
                f"depuis le statut {order.status}."
            )

        items = list(order.items.select_related("variant"))

        for item in items:
            if item.variant_id is None:
                raise ValueError(
                    f"La variante de l'article {item.sku} "
                    "n'existe plus."
                )

            stock = (
                Stock.objects.select_for_update()
                .get(variant_id=item.variant_id)
            )

            if (
                stock.reserved_quantity < item.quantity
                or stock.quantity < item.quantity
            ):
                raise ValueError(
                    f"Stock incohérent pour {item.sku}. "
                    "Vérifie la réservation avant de continuer."
                )

            stock.quantity -= item.quantity
            stock.reserved_quantity -= item.quantity
            stock.save(
                update_fields=[
                    "quantity",
                    "reserved_quantity",
                    "updated_at",
                ]
            )

            StockMovement.objects.create(
                stock=stock,
                movement_type=StockMovement.MOVEMENT_OUT,
                quantity=item.quantity,
                reason=f"Commande payée {order.reference}",
            )

        order.status = Order.Status.CONFIRMED
        order.save(update_fields=["status", "updated_at"])

    @classmethod
    def _release_order_stock(cls, order):
        """
        Libère les quantités réservées pour une commande
        qui ne sera pas honorée.
        L'appelant doit verrouiller la commande.
        """
        if order.status != Order.Status.PENDING:
            return

        items = list(order.items.select_related("variant"))

        for item in items:
            if item.variant_id is None:
                continue

            stock = (
                Stock.objects.select_for_update()
                .get(variant_id=item.variant_id)
            )

            if stock.reserved_quantity < item.quantity:
                raise ValueError(
                    f"Réservation incohérente pour {item.sku}. "
                    "Aucune quantité n'a été modifiée."
                )

            stock.reserved_quantity -= item.quantity
            stock.save(
                update_fields=[
                    "reserved_quantity",
                    "updated_at",
                ]
            )

        order.status = Order.Status.CANCELLED
        order.save(update_fields=["status", "updated_at"])


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

        if order.status != Order.Status.PENDING:
            raise ValueError(
                "Seule une commande en attente de paiement "
                "peut être payée "
                f"(statut actuel : {order.status})."
            )

        if order.payments.filter(
            status=Payment.Status.SUCCESS
        ).exists():
            raise ValueError(
                "Cette commande est déjà payée."
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
        # 2 bis. Vérifier la disponibilité dans le pays
        # --------------------------------------------------

        try:
            shipping_address = order.shipping_address
        except ObjectDoesNotExist:
            shipping_address = None

        if (
            shipping_address is not None
            and shipping_address.country_code
        ):
            country = (
                Country.objects
                .filter(
                    code__iexact=shipping_address.country_code,
                    is_active=True,
                )
                .first()
            )

            if (
                country is not None
                and payment_method.countries.exists()
                and not country.payment_methods.filter(
                    pk=payment_method.pk
                ).exists()
            ):
                raise ValueError(
                    "Ce moyen de paiement n'est pas disponible "
                    f"pour {country.name}."
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
        payment = (
            Payment.objects.select_for_update()
            .select_related("order")
            .get(pk=payment.pk)
        )

        order = (
            Order.objects.select_for_update()
            .get(pk=payment.order_id)
        )

        if payment.status == Payment.Status.SUCCESS:
            return payment

        if payment.status in [
            Payment.Status.FAILED,
            Payment.Status.CANCELLED,
            Payment.Status.REFUNDED,
        ]:
            raise ValueError(
                "Ce paiement possède déjà un statut terminal. "
                "Une vérification manuelle est nécessaire "
                "avant toute réconciliation."
            )

        cls._finalize_order_stock(order)

        payment.status = Payment.Status.SUCCESS
        payment.paid_at = timezone.now()
        payment.save(
            update_fields=["status", "paid_at", "updated_at"]
        )

        transaction_obj = (
            payment.transactions.order_by("-created_at").first()
        )

        if transaction_obj:
            transaction_obj.status = Transaction.Status.SUCCESS

            if external_reference:
                transaction_obj.external_reference = external_reference

            transaction_obj.response_message = response_message
            transaction_obj.transaction_date = timezone.now()
            transaction_obj.save(
                update_fields=[
                    "status",
                    "external_reference",
                    "response_message",
                    "transaction_date",
                ]
            )

        NotificationService.payment_succeeded(payment)
        NotificationService.order_confirmed(order)

        return payment

    
    
    
    @classmethod
    @transaction.atomic
    def mark_payment_failed(
        cls,
        *,
        payment,
        response_message=None,
    ):
        payment = (
            Payment.objects.select_for_update()
            .select_related("order")
            .get(pk=payment.pk)
        )

        order = (
            Order.objects.select_for_update()
            .get(pk=payment.order_id)
        )

        # Un même événement peut être traité plusieurs fois.
        if payment.status == Payment.Status.FAILED:
            return payment

        # Empêcher toute transition depuis un statut terminal incompatible.
        if payment.status in [
            Payment.Status.SUCCESS,
            Payment.Status.REFUNDED,
            Payment.Status.CANCELLED,
        ]:
            raise ValueError(
                "Ce paiement possède déjà un statut terminal "
                "incompatible avec un échec."
            )

        # Une commande confirmée ne doit pas être affectée
        # par un retour d'échec tardif.
        if order.status != Order.Status.PENDING:
            raise ValueError(
                "Impossible de marquer le paiement comme échoué : "
                f"la commande est au statut {order.status}."
            )

        cls._release_order_stock(order)

        payment.status = Payment.Status.FAILED
        payment.save(update_fields=["status", "updated_at"])

        transaction_obj = (
            payment.transactions.order_by("-created_at").first()
        )

        if transaction_obj:
            transaction_obj.status = Transaction.Status.FAILED
            transaction_obj.response_message = response_message
            transaction_obj.transaction_date = timezone.now()
            transaction_obj.save(
                update_fields=[
                    "status",
                    "response_message",
                    "transaction_date",
                ]
            )

        NotificationService.payment_failed(payment)
        NotificationService.order_cancelled(order)

        return payment
    
    
    @classmethod
    @transaction.atomic
    def mark_payment_cancelled(
        cls,
        *,
        payment,
        response_message=None,
    ):
        payment = (
            Payment.objects.select_for_update()
            .select_related("order")
            .get(pk=payment.pk)
        )

        order = (
            Order.objects.select_for_update()
            .get(pk=payment.order_id)
        )

        # Rendre les répétitions du même événement sans effet.
        if payment.status == Payment.Status.CANCELLED:
            return payment

        if payment.status in [
            Payment.Status.SUCCESS,
            Payment.Status.REFUNDED,
            Payment.Status.FAILED,
        ]:
            raise ValueError(
                "Ce paiement possède déjà un statut terminal "
                "incompatible avec une annulation."
            )

        # Ne pas annuler un paiement si la commande a déjà
        # été confirmée, annulée ou placée dans un autre état.
        if order.status != Order.Status.PENDING:
            raise ValueError(
                "Impossible d'annuler le paiement : "
                f"la commande est au statut {order.status}."
            )

        cls._release_order_stock(order)

        payment.status = Payment.Status.CANCELLED
        payment.save(update_fields=["status", "updated_at"])

        transaction_obj = (
            payment.transactions.order_by("-created_at").first()
        )

        if transaction_obj:
            transaction_obj.status = Transaction.Status.CANCELLED
            transaction_obj.response_message = response_message
            transaction_obj.transaction_date = timezone.now()
            transaction_obj.save(
                update_fields=[
                    "status",
                    "response_message",
                    "transaction_date",
                ]
            )

        NotificationService.order_cancelled(order)

        return payment

    