from django.db.models import F, Max, Min, Q
from django.db.models.functions import Coalesce
from django_filters.rest_framework import DjangoFilterBackend

from rest_framework import viewsets
from rest_framework.filters import OrderingFilter, SearchFilter
from rest_framework.permissions import AllowAny

from apps.accounts.permissions import HasPermission, user_has_permission
from apps.audit.models import AuditLog
from apps.audit.services import AuditService
from apps.notifications.services import NotificationService
from apps.promotions.services import PromotionService
from apps.shipping.services import ShippingService

from .filters import ProductFilter
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
    ProductListSerializer,
    ProductDetailSerializer,
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

        parent = self.request.query_params.get("parent")

        if parent == "root":
            queryset = queryset.filter(parent__isnull=True)

        elif parent:
            if not parent.isdigit():
                return queryset.none()

            queryset = queryset.filter(parent_id=parent)

        search = self.request.query_params.get("search")

        if search:
            queryset = queryset.filter(name__icontains=search)

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

        search = self.request.query_params.get("search")

        if search:
            queryset = queryset.filter(name__icontains=search)

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


class ProductOrderingFilter(OrderingFilter):
    """
    Accepte les alias de tri utilisés par le front :
    price, -price et newest.
    """

    aliases = {
        "price": "base_price",
        "-price": "-base_price",
        "newest": "-created_at",
        "-newest": "created_at",
    }

    def get_ordering(self, request, queryset, view):
        ordering = super().get_ordering(
            request,
            queryset,
            view,
        )

        if not ordering:
            return ordering

        return [
            self.aliases.get(item, item)
            for item in ordering
        ]


class ProductViewSet(viewsets.ModelViewSet):

    filter_backends = [
        DjangoFilterBackend,
        SearchFilter,
        ProductOrderingFilter,
    ]

    filterset_class = ProductFilter

    search_fields = [
        "name",
        "description",
        "brand__name",
        "variants__sku",
        "product_categories__category__name",
    ]

    ordering_fields = [
        "base_price",
        "price",
        "name",
        "created_at",
        "newest",
    ]

    ordering = ["name"]

    def get_queryset(self):

        queryset = (
            Product.objects
            .select_related("brand")
            .prefetch_related(
                "images",
                "product_categories__category",
                "available_countries",
                "variants__stock",
                (
                    "variants__variant_attribute_values"
                    "__attribute_value__attribute"
                ),
            )
            .annotate(
                price_min=Coalesce(
                    Min(
                        "variants__price",
                        filter=Q(variants__is_active=True),
                    ),
                    F("base_price"),
                ),
                price_max=Coalesce(
                    Max(
                        "variants__price",
                        filter=Q(variants__is_active=True),
                    ),
                    F("base_price"),
                ),
            )
            .distinct()
        )

        if not can_manage_catalog(self.request.user):
            queryset = queryset.filter(is_active=True)

        return queryset

    def get_serializer_class(self):
        if self.action == "list":
            return ProductListSerializer

        if self.action == "retrieve":
            return ProductDetailSerializer

        return ProductSerializer

    def get_serializer_context(self):
        context = super().get_serializer_context()
        country_value = self.request.query_params.get("country")
        country = (
            ShippingService.find_country(country_value)
            if country_value
            else None
        )

        context["country"] = country
        context["promotions"] = (
            PromotionService.active_promotions(
                country=country
            )
        )

        return context

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

    def perform_create(self, serializer):
        product = serializer.save()

        NotificationService.new_product(product)

        AuditService.log(
            action=AuditLog.Action.CREATE,
            actor=self.request.user,
            target=product,
            metadata={
                "name": product.name,
                "brand_id": product.brand_id,
            },
            request=self.request,
        )

    def perform_update(self, serializer):
        product = serializer.instance

        before = {
            "name": product.name,
            "base_price": str(product.base_price),
            "is_active": product.is_active,
        }

        product = serializer.save()

        after = {
            "name": product.name,
            "base_price": str(product.base_price),
            "is_active": product.is_active,
        }

        changes = {
            field: {
                "before": before[field],
                "after": after[field],
            }
            for field in before
            if before[field] != after[field]
        }

        AuditService.log(
            action=AuditLog.Action.UPDATE,
            actor=self.request.user,
            target=product,
            changes=changes,
            request=self.request,
        )

    def perform_destroy(self, instance):
        product_id = instance.pk
        product_name = instance.name

        instance.delete()

        AuditService.log(
            action=AuditLog.Action.DELETE,
            actor=self.request.user,
            target_type="catalog.product",
            target_id=str(product_id),
            target_repr=product_name,
            request=self.request,
        )


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

        product = self.request.query_params.get("product")

        if product:
            if not product.isdigit():
                return queryset.none()

            queryset = queryset.filter(product_id=product)

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

    serializer_class = AttributeSerializer

    def get_queryset(self):

        queryset = Attribute.objects.all()

        search = self.request.query_params.get("search")

        if search:
            queryset = queryset.filter(name__icontains=search)

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


class AttributeValueViewSet(viewsets.ModelViewSet):

    serializer_class = AttributeValueSerializer

    def get_queryset(self):

        queryset = AttributeValue.objects.select_related(
            "attribute"
        ).all()

        attribute = self.request.query_params.get("attribute")

        if attribute:
            if not attribute.isdigit():
                return queryset.none()

            queryset = queryset.filter(attribute_id=attribute)

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

        product = self.request.query_params.get("product")

        if product:
            if not product.isdigit():
                return queryset.none()

            queryset = queryset.filter(product_id=product)

        is_active = self.request.query_params.get("is_active")

        if is_active is not None:
            normalized = is_active.strip().lower()

            if normalized not in {"true", "false", "1", "0"}:
                return queryset.none()

            queryset = queryset.filter(
                is_active=normalized in {"true", "1"}
            )

        search = self.request.query_params.get("search")

        if search:
            queryset = queryset.filter(sku__icontains=search)

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
            .order_by("variant_id", "attribute_value_id")
        )

        if not can_manage_catalog(self.request.user):
            queryset = queryset.filter(
                variant__is_active=True,
                variant__product__is_active=True,
            )

        variant = self.request.query_params.get("variant")

        if variant:
            if not variant.isdigit():
                return queryset.none()

            queryset = queryset.filter(variant_id=variant)

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
