from rest_framework import status, viewsets
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .models import Address
from .serializers import AddressSerializer


class AddressViewSet(viewsets.ModelViewSet):

    serializer_class = AddressSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return Address.objects.filter(
            user=self.request.user
        )

    def perform_create(self, serializer):

        address = serializer.save(
            user=self.request.user
        )

        if address.is_default:
            Address.objects.filter(
                user=self.request.user
            ).exclude(
                id=address.id
            ).update(
                is_default=False
            )

    def perform_update(self, serializer):

        address = serializer.save()

        if address.is_default:
            Address.objects.filter(
                user=self.request.user
            ).exclude(
                id=address.id
            ).update(
                is_default=False
            )