from django.urls import path

from rest_framework.routers import DefaultRouter

from .views import (
    DeliveryViewSet,
    ShippingMethodViewSet,
    ShippingQuoteView,
    ShippingRateViewSet,
    ShippingZoneViewSet,
)


router = DefaultRouter()

router.register(
    "shipping-zones",
    ShippingZoneViewSet,
    basename="shipping-zone",
)

router.register(
    "shipping-methods",
    ShippingMethodViewSet,
    basename="shipping-method",
)

router.register(
    "shipping-rates",
    ShippingRateViewSet,
    basename="shipping-rate",
)

router.register(
    "deliveries",
    DeliveryViewSet,
    basename="delivery",
)

urlpatterns = router.urls + [
    path(
        "shipping/quote/",
        ShippingQuoteView.as_view(),
        name="shipping-quote",
    ),
]
