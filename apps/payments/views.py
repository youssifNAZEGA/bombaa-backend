import hashlib
import json
import hmac
from rest_framework.views import APIView
from django.conf import settings
from decimal import Decimal
from .services import PaymentService
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from .models import PaymentMethod, Payment, Transaction
from .serializers import (
    PaymentMethodSerializer,
    PaymentSerializer,
    TransactionSerializer,
)



class PaymentMethodViewSet(viewsets.ModelViewSet):
    serializer_class = PaymentMethodSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return PaymentMethod.objects.filter(
            is_active=True
        ).order_by("name")

class PaymentViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = PaymentSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return (
            Payment.objects
            .filter(
                order__user=self.request.user
            )
            .select_related(
                "order",
                "payment_method",
            )
            .prefetch_related("transactions")
        )

    @action(
        detail=False,
        methods=["post"],
        url_path="create",
    )
    def create_payment(self, request):
        from apps.orders.models import Order

        order_id = request.data.get("order_id")
        payment_method_id = request.data.get(
            "payment_method_id"
        )

        if not order_id:
            return Response(
                {
                    "detail": (
                        "Le champ order_id est obligatoire."
                    )
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        if not payment_method_id:
            return Response(
                {
                    "detail": (
                        "Le champ payment_method_id "
                        "est obligatoire."
                    )
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            order = Order.objects.get(
                pk=order_id,
                user=request.user,
            )
        except Order.DoesNotExist:
            return Response(
                {
                    "detail": "Commande introuvable."
                },
                status=status.HTTP_404_NOT_FOUND,
            )

        try:
            payment_method = PaymentMethod.objects.get(
                pk=payment_method_id,
                is_active=True,
            )
        except PaymentMethod.DoesNotExist:
            return Response(
                {
                    "detail": (
                        "Moyen de paiement introuvable "
                        "ou désactivé."
                    )
                },
                status=status.HTTP_404_NOT_FOUND,
            )

        try:
            payment = PaymentService.create_payment(
                order=order,
                payment_method=payment_method,
            )

        except ValueError as exc:
            return Response(
                {
                    "detail": str(exc)
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        serializer = self.get_serializer(payment)

        return Response(
            serializer.data,
            status=status.HTTP_201_CREATED,
        )

class TransactionViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = TransactionSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return (
            Transaction.objects
            .filter(
                payment__order__user=self.request.user
            )
            .select_related("payment")
        )



class PayDunyaIPNView(APIView):
    """
    Endpoint public appelé par PayDunya après une tentative de paiement.

    URL :
    POST /api/payments/webhooks/paydunya/
    """

    authentication_classes = []
    permission_classes = []

    def post(self, request):
        master_key = settings.PAYDUNYA_MASTER_KEY

        if not master_key:
            return Response(
                {
                    "detail": "La configuration PayDunya est incomplète."
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        data = self._extract_data(request)

        if not data:
            return Response(
                {
                    "detail": "Données IPN PayDunya introuvables."
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        received_hash = data.get("hash")

        if not received_hash:
            return Response(
                {
                    "detail": "Hash PayDunya manquant."
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        expected_hash = hashlib.sha512(
            master_key.encode("utf-8")
        ).hexdigest()

        if not hmac.compare_digest(
            received_hash,
            expected_hash
        ):
            return Response(
                {
                    "detail": "Signature PayDunya invalide."
                },
                status=status.HTTP_403_FORBIDDEN,
            )

        payment_status = str(
            data.get("status", "")
        ).lower()

        custom_data = data.get("custom_data") or {}

        payment_reference = custom_data.get(
            "payment_reference"
        )

        if not payment_reference:
            return Response(
                {
                    "detail": "Référence du paiement introuvable."
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            payment = Payment.objects.select_related(
                "order"
            ).get(
                reference=payment_reference
            )
        except Payment.DoesNotExist:
            return Response(
                {
                    "detail": "Paiement BOMBAA introuvable."
                },
                status=status.HTTP_404_NOT_FOUND,
            )

        invoice = data.get("invoice") or {}

        received_amount = invoice.get("total_amount")

        if received_amount is not None:
            try:
                received_amount = Decimal(
                    str(received_amount)
                )
            except Exception:
                return Response(
                    {
                        "detail": "Montant PayDunya invalide."
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )

            if received_amount != payment.amount:
                return Response(
                    {
                        "detail": "Le montant PayDunya ne correspond pas au paiement BOMBAA."
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )

        provider_token = invoice.get("token")

        transaction_obj = (
            payment.transactions
            .order_by("-created_at")
            .first()
        )

        if transaction_obj and provider_token:
            transaction_obj.external_reference = provider_token
            transaction_obj.response_message = (
                data.get("response_text")
            )
            transaction_obj.save(
                update_fields=[
                    "external_reference",
                    "response_message",
                ]
            )

        if payment_status == "completed":
            PaymentService.mark_payment_success(
                payment=payment,
                external_reference=provider_token,
                response_message=data.get("response_text"),
            )

        elif payment_status == "failed":
            PaymentService.mark_payment_failed(
                payment=payment,
                response_message=data.get("fail_reason")
                or data.get("response_text"),
            )

        elif payment_status == "cancelled":
            PaymentService.mark_payment_failed(
                payment=payment,
                response_message="Paiement annulé par PayDunya.",
            )

        elif payment_status == "pending":
            if payment.status == Payment.Status.PENDING:
                PaymentService.mark_payment_processing(
                    payment=payment
                )

        else:
            return Response(
                {
                    "detail": (
                        f"Statut PayDunya non pris en charge : "
                        f"{payment_status}"
                    )
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        return Response(
            {
                "success": True,
                "payment_reference": payment.reference,
                "status": payment.status,
            },
            status=status.HTTP_200_OK,
        )

    @staticmethod
    def _extract_data(request):
        """
        PayDunya envoie l'IPN en application/x-www-form-urlencoded.

        Cette méthode accepte :
        - data sous forme JSON ;
        - data sous forme de dictionnaire ;
        - JSON brut en fallback.
        """

        raw_data = request.POST.get("data")

        if raw_data:
            if isinstance(raw_data, dict):
                return raw_data

            if isinstance(raw_data, str):
                try:
                    parsed = json.loads(raw_data)

                    if isinstance(parsed, dict):
                        return parsed

                except json.JSONDecodeError:
                    pass

        if "data" in request.data:
            data = request.data["data"]

            if isinstance(data, dict):
                return data

            if isinstance(data, str):
                try:
                    parsed = json.loads(data)

                    if isinstance(parsed, dict):
                        return parsed

                except json.JSONDecodeError:
                    pass

        if request.content_type == "application/json":
            if isinstance(request.data, dict):
                return request.data.get(
                    "data",
                    request.data,
                )

        return {}