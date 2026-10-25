from rest_framework.routers import DefaultRouter

from .views import CouponViewSet, PromotionViewSet


router = DefaultRouter()

router.register(
    "promotions",
    PromotionViewSet,
    basename="promotion",
)

router.register(
    "coupons",
    CouponViewSet,
    basename="coupon",
)

urlpatterns = router.urls
