from rest_framework.routers import DefaultRouter

from .views import (
    PaymentMethodViewSet,
    PaymentViewSet,
    TransactionViewSet,
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

urlpatterns = router.urls