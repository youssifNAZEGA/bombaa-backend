from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated

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
            .filter(order__user=self.request.user)
            .select_related(
                "order",
                "payment_method",
            )
            .prefetch_related("transactions")
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