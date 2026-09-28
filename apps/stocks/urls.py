from rest_framework.routers import DefaultRouter
from .views import StockViewSet, StockMovementViewSet

router = DefaultRouter()

router.register(
    "stocks",
    StockViewSet,
    basename="stock",
)

router.register(
    "stock-movements",
    StockMovementViewSet,
    basename="stock-movement",
)


urlpatterns = router.urls