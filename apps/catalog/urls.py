from rest_framework.routers import DefaultRouter

from .views import (
    CategoryViewSet, 
    BrandViewSet, 
    ProductViewSet, 
    ProductImageViewSet,
    AttributeViewSet,
    AttributeValueViewSet,
    ProductVariantViewSet,
    VariantAttributeValueViewSet,
    )


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

router.register(
    "products",
    ProductViewSet,
    basename="product",
)

router.register(
    "product-images",
    ProductImageViewSet,
    basename="product-image",
)

router.register(
    "attributes",
    AttributeViewSet,
    basename="attribute",
)

router.register(
    "attribute-values",
    AttributeValueViewSet,
    basename="attribute-value",
)

router.register(
    "product-variants",
    ProductVariantViewSet,
    basename="product-variant",
)

router.register(
    "variant-attribute-values",
    VariantAttributeValueViewSet,
    basename="variant-attribute-value",
)

urlpatterns = router.urls