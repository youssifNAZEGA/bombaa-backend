from rest_framework import viewsets

from apps.accounts.permissions import HasPermission

from .models import Category, Brand,  Product
from .serializers import CategorySerializer, BrandSerializer,ProductSerializer


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