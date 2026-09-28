from rest_framework import viewsets

from apps.accounts.permissions import HasPermission

from .models import (
    Category, 
    Brand,  
    Product, 
    ProductImage,
    Attribute,
    AttributeValue,
    ProductVariant,
    VariantAttributeValue,
    )
from .serializers import (
    CategorySerializer, 
    BrandSerializer,
    ProductSerializer, 
    ProductImageSerializer,
    AttributeSerializer,
    AttributeValueSerializer,
    ProductVariantSerializer,
    VariantAttributeValueSerializer,
    )


class CategoryViewSet(viewsets.ModelViewSet):

    queryset = Category.objects.all()

    serializer_class = CategorySerializer

    def get_permissions(self):

        if self.action == "list":
            permission = "categories.view"

        elif self.action == "retrieve":
            permission = "categories.view"

        elif self.action == "create":
            permission = "categories.create"

        elif self.action in ["update", "partial_update"]:
            permission = "categories.update"

        elif self.action == "destroy":
            permission = "categories.delete"

        else:
            permission = "categories.view"

        return [
            HasPermission(permission)()
        ]


class BrandViewSet(viewsets.ModelViewSet):

    queryset = Brand.objects.all()
    serializer_class = BrandSerializer

    def get_permissions(self):

        if self.action == "list":
            permission = "brands.view"

        elif self.action == "retrieve":
            permission = "brands.view"

        elif self.action == "create":
            permission = "brands.create"

        elif self.action in ["update", "partial_update"]:
            permission = "brands.update"

        elif self.action == "destroy":
            permission = "brands.delete"

        else:
            permission = "brands.view"

        return [
            HasPermission(permission)()
        ]


class ProductViewSet(viewsets.ModelViewSet):

    queryset = Product.objects.select_related(
        "brand"
    ).all()

    serializer_class = ProductSerializer

    def get_permissions(self):

        if self.action in ["list", "retrieve"]:
            permission = "products.view"

        elif self.action == "create":
            permission = "products.create"

        elif self.action in ["update", "partial_update"]:
            permission = "products.update"

        elif self.action == "destroy":
            permission = "products.delete"

        else:
            permission = "products.view"

        return [
            HasPermission(permission)()
        ]

class ProductImageViewSet(viewsets.ModelViewSet):

    queryset = ProductImage.objects.select_related(
        "product"
    ).all()

    serializer_class = ProductImageSerializer

    def get_permissions(self):

        if self.action in ["list", "retrieve"]:
            permission = "products.view"

        elif self.action == "create":
            permission = "products.update"

        elif self.action in ["update", "partial_update"]:
            permission = "products.update"

        elif self.action == "destroy":
            permission = "products.update"

        else:
            permission = "products.view"

        return [
            HasPermission(permission)()
        ]

    def perform_create(self, serializer):

        image = serializer.save()

        if image.is_primary:

            ProductImage.objects.filter(
                product=image.product
            ).exclude(
                id=image.id
            ).update(
                is_primary=False
            )

    def perform_update(self, serializer):

        image = serializer.save()

        if image.is_primary:

            ProductImage.objects.filter(
                product=image.product
            ).exclude(
                id=image.id
            ).update(
                is_primary=False
            )


class AttributeViewSet(viewsets.ModelViewSet):

    queryset = Attribute.objects.all()

    serializer_class = AttributeSerializer

    def get_permissions(self):

        if self.action in ["list", "retrieve"]:
            permission = "products.view"

        elif self.action == "create":
            permission = "products.create"

        elif self.action in ["update", "partial_update"]:
            permission = "products.update"

        elif self.action == "destroy":
            permission = "products.delete"

        else:
            permission = "products.view"

        return [
            HasPermission(permission)()
        ]

class AttributeValueViewSet(viewsets.ModelViewSet):

    queryset = AttributeValue.objects.select_related(
        "attribute"
    ).all()

    serializer_class = AttributeValueSerializer

    def get_permissions(self):

        if self.action in ["list", "retrieve"]:
            permission = "products.view"

        elif self.action == "create":
            permission = "products.create"

        elif self.action in ["update", "partial_update"]:
            permission = "products.update"

        elif self.action == "destroy":
            permission = "products.delete"

        else:
            permission = "products.view"

        return [
            HasPermission(permission)()
        ]


class ProductVariantViewSet(viewsets.ModelViewSet):

    queryset = ProductVariant.objects.select_related(
        "product"
    ).all()

    serializer_class = ProductVariantSerializer

    def get_permissions(self):

        if self.action in ["list", "retrieve"]:
            permission = "products.view"

        elif self.action == "create":
            permission = "products.create"

        elif self.action in ["update", "partial_update"]:
            permission = "products.update"

        elif self.action == "destroy":
            permission = "products.delete"

        else:
            permission = "products.view"

        return [
            HasPermission(permission)()
        ]

class VariantAttributeValueViewSet(viewsets.ModelViewSet):

    queryset = (
        VariantAttributeValue.objects
        .select_related(
            "variant",
            "attribute_value",
            "attribute_value__attribute",
        )
        .all()
    )

    serializer_class = VariantAttributeValueSerializer

    def get_permissions(self):

        if self.action in ["list", "retrieve"]:
            permission = "products.view"

        elif self.action == "create":
            permission = "products.create"

        elif self.action in [
            "update",
            "partial_update",
        ]:
            permission = "products.update"

        elif self.action == "destroy":
            permission = "products.delete"

        else:
            permission = "products.view"

        return [
            HasPermission(permission)()
        ]