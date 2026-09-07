from rest_framework import viewsets

from apps.accounts.permissions import HasPermission

from .models import Category
from .serializers import CategorySerializer


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