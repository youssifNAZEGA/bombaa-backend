from rest_framework import viewsets
from rest_framework.permissions import AllowAny

from apps.accounts.permissions import HasPermission, user_has_permission

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


def can_manage_catalog(user):
    """
    Indique si l'utilisateur peut consulter les éléments
    inactifs du catalogue (staff ou permission products.update).
    """

    if not user or not user.is_authenticated:
        return False

    return (
        user.is_staff
        or user_has_permission(user, "products.update")
    )


class CategoryViewSet(viewsets.ModelViewSet):

    serializer_class = CategorySerializer

    def get_queryset(self):

        queryset = Category.objects.all()

        if not can_manage_catalog(self.request.user):
            queryset = queryset.filter(is_active=True)

        return queryset

    def get_permissions(self):

        if self.action in ["list", "retrieve"]:
            return [AllowAny()]

        if self.action == "create":
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

    serializer_class = BrandSerializer

    def get_queryset(self):

        queryset = Brand.objects.all()

        if not can_manage_catalog(self.request.user):
            queryset = queryset.filter(is_active=True)

        return queryset

    def get_permissions(self):

        if self.action in ["list", "retrieve"]:
            return [AllowAny()]

        if self.action == "create":
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

    serializer_class = ProductSerializer

    def get_queryset(self):

        queryset = Product.objects.select_related(
            "brand"
        ).all()

        if not can_manage_catalog(self.request.user):
            queryset = queryset.filter(is_active=True)

        return queryset

    def get_permissions(self):

        if self.action in ["list", "retrieve"]:
            return [AllowAny()]

        if self.action == "create":
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

    serializer_class = ProductImageSerializer

    def get_queryset(self):

        queryset = ProductImage.objects.select_related(
            "product"
        ).all()

        if not can_manage_catalog(self.request.user):
            queryset = queryset.filter(
                product__is_active=True
            )

        return queryset

    def get_permissions(self):

        if self.action in ["list", "retrieve"]:
            return [AllowAny()]

        if self.action == "create":
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
            return [AllowAny()]

        if self.action == "create":
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
            return [AllowAny()]

        if self.action == "create":
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

    serializer_class = ProductVariantSerializer

    def get_queryset(self):

        queryset = ProductVariant.objects.select_related(
            "product"
        ).all()

        if not can_manage_catalog(self.request.user):
            queryset = queryset.filter(
                is_active=True,
                product__is_active=True,
            )

        return queryset

    def get_permissions(self):

        if self.action in ["list", "retrieve"]:
            return [AllowAny()]

        if self.action == "create":
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

    serializer_class = VariantAttributeValueSerializer

    def get_queryset(self):

        queryset = (
            VariantAttributeValue.objects
            .select_related(
                "variant",
                "attribute_value",
                "attribute_value__attribute",
            )
            .all()
        )

        if not can_manage_catalog(self.request.user):
            queryset = queryset.filter(
                variant__is_active=True,
                variant__product__is_active=True,
            )

        return queryset

    def get_permissions(self):

        if self.action in ["list", "retrieve"]:
            return [AllowAny()]

        if self.action == "create":
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
