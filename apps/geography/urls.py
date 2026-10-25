from rest_framework.routers import DefaultRouter

from .views import CountryViewSet, CurrencyViewSet


router = DefaultRouter()

router.register(
    "countries",
    CountryViewSet,
    basename="country",
)

router.register(
    "currencies",
    CurrencyViewSet,
    basename="currency",
)

urlpatterns = router.urls
