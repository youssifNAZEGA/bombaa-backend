from rest_framework.routers import DefaultRouter

from .views import RefundViewSet, ReturnRequestViewSet


router = DefaultRouter()

router.register(
    "returns",
    ReturnRequestViewSet,
    basename="return-request",
)

router.register(
    "refunds",
    RefundViewSet,
    basename="refund",
)

urlpatterns = router.urls
