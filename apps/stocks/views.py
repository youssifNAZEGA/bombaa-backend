from rest_framework import viewsets

from apps.accounts.permissions import HasPermission
from apps.audit.models import AuditLog
from apps.audit.services import AuditService
from apps.notifications.services import NotificationService

from .models import Stock, StockMovement

from .serializers import StockSerializer, StockMovementSerializer


class StockViewSet(viewsets.ModelViewSet):

    queryset = (
        Stock.objects
        .select_related(
            "variant",
            "variant__product",
        )
        .all()
    )

    serializer_class = StockSerializer

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

    def perform_create(self, serializer):
        stock = serializer.save()

        AuditService.log(
            action=AuditLog.Action.CREATE,
            actor=self.request.user,
            target=stock,
            metadata={
                "variant_id": stock.variant_id,
                "quantity": stock.quantity,
            },
            request=self.request,
        )

    def perform_update(self, serializer):
        stock = serializer.instance

        before = {
            "quantity": stock.quantity,
            "reserved_quantity": stock.reserved_quantity,
            "minimum_quantity": stock.minimum_quantity,
        }

        previous_available = (
            stock.quantity - stock.reserved_quantity
        )

        stock = serializer.save()

        current_available = (
            stock.quantity - stock.reserved_quantity
        )

        if previous_available <= 0 < current_available:
            NotificationService.back_in_stock(
                stock.variant
            )

        after = {
            "quantity": stock.quantity,
            "reserved_quantity": stock.reserved_quantity,
            "minimum_quantity": stock.minimum_quantity,
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
            target=stock,
            changes=changes,
            request=self.request,
        )

    def perform_destroy(self, instance):
        stock_id = instance.pk
        target_repr = str(instance)

        instance.delete()

        AuditService.log(
            action=AuditLog.Action.DELETE,
            actor=self.request.user,
            target_type="stocks.stock",
            target_id=str(stock_id),
            target_repr=target_repr,
            request=self.request,
        )


class StockMovementViewSet(viewsets.ModelViewSet):
    queryset = StockMovement.objects.select_related(
        "stock",
        "stock__variant",
    )
    serializer_class = StockMovementSerializer

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

        return [HasPermission(permission)()]