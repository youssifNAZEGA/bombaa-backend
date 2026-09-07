from rest_framework.routers import DefaultRouter

from .views import CategoryViewSet, BrandViewSet


router = DefaultRouter()

router.register(
    "categories",
    CategoryViewSet,
    basename="category",
)

router.register(
    "brands",
    BrandViewSet,
    basename="brand",
)

urlpatterns = router.urls