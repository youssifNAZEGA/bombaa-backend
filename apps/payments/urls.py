from rest_framework.routers import DefaultRouter
from django.urls import path
from .views import (
    PaymentMethodViewSet,
    PaymentViewSet,
    TransactionViewSet,
    PayDunyaIPNView,
)


router = DefaultRouter()

router.register(
    "payment-methods",
    PaymentMethodViewSet,
    basename="payment-method",
)

router.register(
    "payments",
    PaymentViewSet,
    basename="payment",
)

router.register(
    "transactions",
    TransactionViewSet,
    basename="transaction",
)

urlpatterns = router.urls + [
    path(
        "payments/webhooks/paydunya/",
        PayDunyaIPNView.as_view(),
        name="paydunya-ipn",
    ),
]