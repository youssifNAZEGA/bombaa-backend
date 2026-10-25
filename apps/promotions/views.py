from django.db.models import Q
from django.utils import timezone

from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from apps.accounts.permissions import (
    HasPermission,
    user_has_permission,
)
from apps.audit.models import AuditLog
from apps.audit.services import AuditService
from apps.catalog.models import Product
from apps.notifications.services import NotificationService
from apps.shipping.services import ShippingService

from .models import Coupon, DiscountType, Promotion
from .serializers import CouponSerializer, PromotionSerializer


def can_manage_promotions(user):
    if not user or not user.is_authenticated:
        return False

    return (
        user.is_staff
        or user_has_permission(user, "promotions.update")
    )


def can_manage_coupons(user):
    if not user or not user.is_authenticated:
        return False

    return (
        user.is_staff
        or user_has_permission(user, "coupons.update")
    )


def _discount_label(discount):
    if discount.discount_type == DiscountType.PERCENTAGE:
        return f"-{discount.value}%"

    return f"-{discount.value}"


def _filter_country(queryset, value):
    country = ShippingService.find_country(value)

    if country is None:
        return queryset.none()

    return queryset.filter(
        Q(countries__isnull=True)
        | Q(countries=country)
    ).distinct()


class PromotionViewSet(viewsets.ModelViewSet):
    serializer_class = PromotionSerializer

    def get_permissions(self):
        if self.action in ["list", "retrieve"]:
            return [AllowAny()]

        if self.action == "create":
            permission = "promotions.create"
        elif self.action in [
            "update",
            "partial_update",
            "activate",
            "deactivate",
            "notify",
        ]:
            permission = "promotions.update"
        elif self.action == "destroy":
            permission = "promotions.delete"
        else:
            permission = "promotions.view"

        return [HasPermission(permission)()]

    def get_queryset(self):
        queryset = (
            Promotion.objects
            .prefetch_related(
                "products",
                "categories",
                "brands",
                "countries",
            )
        )

        if not can_manage_promotions(self.request.user):
            now = timezone.now()
            queryset = (
                queryset
                .filter(is_active=True)
                .filter(
                    Q(starts_at__isnull=True)
                    | Q(starts_at__lte=now)
                )
                .filter(
                    Q(ends_at__isnull=True)
                    | Q(ends_at__gte=now)
                )
            )

        country = self.request.query_params.get("country")

        if country:
            queryset = _filter_country(queryset, country)

        product = self.request.query_params.get("product")

        if product:
            if not product.isdigit():
                return queryset.none()

            queryset = queryset.filter(
                products__id=int(product)
            )

        category = self.request.query_params.get("category")

        if category:
            if not category.isdigit():
                return queryset.none()

            queryset = queryset.filter(
                categories__id=int(category)
            )

        brand = self.request.query_params.get("brand")

        if brand:
            if not brand.isdigit():
                return queryset.none()

            queryset = queryset.filter(
                brands__id=int(brand)
            )

        is_active = self.request.query_params.get("is_active")

        if (
            is_active is not None
            and can_manage_promotions(self.request.user)
        ):
            queryset = queryset.filter(
                is_active=is_active.lower()
                in {"1", "true", "yes", "on"}
            )

        search = self.request.query_params.get("search")

        if search:
            queryset = queryset.filter(
                Q(name__icontains=search)
                | Q(description__icontains=search)
            )

        return queryset.distinct()

    def perform_create(self, serializer):
        promotion = serializer.save()

        AuditService.log(
            action=AuditLog.Action.CREATE,
            actor=self.request.user,
            target=promotion,
            metadata={
                "name": promotion.name,
                "discount_type": promotion.discount_type,
                "value": str(promotion.value),
            },
            request=self.request,
        )

        if promotion.is_running():
            self._notify_promotion(promotion)

    def perform_update(self, serializer):
        promotion = serializer.instance

        before = {
            "name": promotion.name,
            "discount_type": promotion.discount_type,
            "value": str(promotion.value),
            "is_active": promotion.is_active,
            "starts_at": (
                promotion.starts_at.isoformat()
                if promotion.starts_at
                else None
            ),
            "ends_at": (
                promotion.ends_at.isoformat()
                if promotion.ends_at
                else None
            ),
        }

        promotion = serializer.save()

        after = {
            "name": promotion.name,
            "discount_type": promotion.discount_type,
            "value": str(promotion.value),
            "is_active": promotion.is_active,
            "starts_at": (
                promotion.starts_at.isoformat()
                if promotion.starts_at
                else None
            ),
            "ends_at": (
                promotion.ends_at.isoformat()
                if promotion.ends_at
                else None
            ),
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
            target=promotion,
            changes=changes,
            request=self.request,
        )

    def perform_destroy(self, instance):
        promotion_id = instance.pk
        promotion_name = instance.name

        instance.delete()

        AuditService.log(
            action=AuditLog.Action.DELETE,
            actor=self.request.user,
            target_type="promotions.promotion",
            target_id=str(promotion_id),
            target_repr=promotion_name,
            request=self.request,
        )

    @action(
        detail=True,
        methods=["post"],
        url_path="activate",
    )
    def activate(self, request, pk=None):
        promotion = self.get_object()
        promotion.is_active = True
        promotion.save(
            update_fields=[
                "is_active",
                "updated_at",
            ]
        )

        AuditService.log(
            action=AuditLog.Action.ACTIVATE,
            actor=request.user,
            target=promotion,
            metadata={"name": promotion.name},
            request=request,
        )

        if promotion.is_running():
            self._notify_promotion(promotion)

        return Response(
            PromotionSerializer(
                promotion,
                context=self.get_serializer_context(),
            ).data
        )

    @action(
        detail=True,
        methods=["post"],
        url_path="deactivate",
    )
    def deactivate(self, request, pk=None):
        promotion = self.get_object()
        promotion.is_active = False
        promotion.save(
            update_fields=[
                "is_active",
                "updated_at",
            ]
        )

        AuditService.log(
            action=AuditLog.Action.DEACTIVATE,
            actor=request.user,
            target=promotion,
            metadata={"name": promotion.name},
            request=request,
        )

        return Response(
            PromotionSerializer(
                promotion,
                context=self.get_serializer_context(),
            ).data
        )

    @action(
        detail=True,
        methods=["post"],
        url_path="notify",
    )
    def notify(self, request, pk=None):
        promotion = self.get_object()
        count = self._notify_promotion(promotion)

        return Response(
            {
                "detail": "Notification envoyée.",
                "notifications_created": count,
            }
        )

    def _notify_promotion(self, promotion):
        product = promotion.products.first()

        if product is None:
            category = promotion.categories.first()

            if category is not None:
                product = (
                    Product.objects
                    .filter(
                        product_categories__category=category,
                        is_active=True,
                    )
                    .first()
                )

        label = _discount_label(promotion)
        message = promotion.description or (
            "Profitez de notre nouvelle promotion"
            f" ({label})."
        )

        return NotificationService.promotion(
            product=product,
            title=f"Promotion : {promotion.name}",
            message=message,
            data={
                "promotion_id": promotion.id,
                "name": promotion.name,
                "discount_type": promotion.discount_type,
                "value": str(promotion.value),
                "discount_label": label,
                "ends_at": (
                    promotion.ends_at.isoformat()
                    if promotion.ends_at
                    else None
                ),
            },
        )


class CouponViewSet(viewsets.ModelViewSet):
    serializer_class = CouponSerializer

    def get_permissions(self):
        if self.action in ["list", "retrieve"]:
            permission = "coupons.view"
        elif self.action == "create":
            permission = "coupons.create"
        elif self.action in [
            "update",
            "partial_update",
            "activate",
            "deactivate",
            "notify",
        ]:
            permission = "coupons.update"
        elif self.action == "destroy":
            permission = "coupons.delete"
        else:
            permission = "coupons.view"

        return [HasPermission(permission)()]

    def get_queryset(self):
        queryset = (
            Coupon.objects
            .prefetch_related(
                "products",
                "categories",
                "countries",
            )
        )

        country = self.request.query_params.get("country")

        if country:
            queryset = _filter_country(queryset, country)

        product = self.request.query_params.get("product")

        if product:
            if not product.isdigit():
                return queryset.none()

            queryset = queryset.filter(
                products__id=int(product)
            )

        category = self.request.query_params.get("category")

        if category:
            if not category.isdigit():
                return queryset.none()

            queryset = queryset.filter(
                categories__id=int(category)
            )

        is_active = self.request.query_params.get("is_active")

        if is_active is not None:
            queryset = queryset.filter(
                is_active=is_active.lower()
                in {"1", "true", "yes", "on"}
            )

        search = self.request.query_params.get("search")

        if search:
            queryset = queryset.filter(
                Q(code__icontains=search)
                | Q(description__icontains=search)
            )

        return queryset.distinct()

    def perform_create(self, serializer):
        coupon = serializer.save()

        AuditService.log(
            action=AuditLog.Action.CREATE,
            actor=self.request.user,
            target=coupon,
            metadata={
                "code": coupon.code,
                "discount_type": coupon.discount_type,
                "value": str(coupon.value),
            },
            request=self.request,
        )

        if coupon.is_running():
            self._notify_coupon(coupon)

    def perform_update(self, serializer):
        coupon = serializer.instance

        before = {
            "code": coupon.code,
            "discount_type": coupon.discount_type,
            "value": str(coupon.value),
            "minimum_amount": str(coupon.minimum_amount),
            "max_uses": coupon.max_uses,
            "is_active": coupon.is_active,
        }

        coupon = serializer.save()

        after = {
            "code": coupon.code,
            "discount_type": coupon.discount_type,
            "value": str(coupon.value),
            "minimum_amount": str(coupon.minimum_amount),
            "max_uses": coupon.max_uses,
            "is_active": coupon.is_active,
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
            target=coupon,
            changes=changes,
            request=self.request,
        )

    def destroy(self, request, *args, **kwargs):
        coupon = self.get_object()

        if coupon.redemptions.exists():
            return Response(
                {
                    "detail": (
                        "Ce coupon a déjà été utilisé. "
                        "Désactivez-le plutôt que de le supprimer."
                    )
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        coupon_id = coupon.pk
        code = coupon.code
        coupon.delete()

        AuditService.log(
            action=AuditLog.Action.DELETE,
            actor=request.user,
            target_type="promotions.coupon",
            target_id=str(coupon_id),
            target_repr=code,
            request=request,
        )

        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(
        detail=True,
        methods=["post"],
        url_path="activate",
    )
    def activate(self, request, pk=None):
        coupon = self.get_object()
        coupon.is_active = True
        coupon.save(
            update_fields=[
                "is_active",
                "updated_at",
            ]
        )

        AuditService.log(
            action=AuditLog.Action.ACTIVATE,
            actor=request.user,
            target=coupon,
            metadata={"code": coupon.code},
            request=request,
        )

        if coupon.is_running():
            self._notify_coupon(coupon)

        return Response(
            CouponSerializer(
                coupon,
                context=self.get_serializer_context(),
            ).data
        )

    @action(
        detail=True,
        methods=["post"],
        url_path="deactivate",
    )
    def deactivate(self, request, pk=None):
        coupon = self.get_object()
        coupon.is_active = False
        coupon.save(
            update_fields=[
                "is_active",
                "updated_at",
            ]
        )

        AuditService.log(
            action=AuditLog.Action.DEACTIVATE,
            actor=request.user,
            target=coupon,
            metadata={"code": coupon.code},
            request=request,
        )

        return Response(
            CouponSerializer(
                coupon,
                context=self.get_serializer_context(),
            ).data
        )

    @action(
        detail=True,
        methods=["post"],
        url_path="notify",
    )
    def notify(self, request, pk=None):
        coupon = self.get_object()
        count = self._notify_coupon(coupon)

        return Response(
            {
                "detail": "Notification envoyée.",
                "notifications_created": count,
            }
        )

    def _notify_coupon(self, coupon):
        label = _discount_label(coupon)
        message = coupon.description or (
            f"Utilisez le code {coupon.code} et profitez "
            f"d'une réduction ({label})."
        )

        return NotificationService.new_coupon(
            title=f"Nouveau coupon : {coupon.code}",
            message=message,
            data={
                "coupon_id": coupon.id,
                "code": coupon.code,
                "discount_type": coupon.discount_type,
                "value": str(coupon.value),
                "discount_label": label,
                "minimum_amount": str(coupon.minimum_amount),
                "ends_at": (
                    coupon.ends_at.isoformat()
                    if coupon.ends_at
                    else None
                ),
            },
        )
