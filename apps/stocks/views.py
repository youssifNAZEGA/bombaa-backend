from rest_framework import viewsets

from apps.accounts.permissions import HasPermission

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