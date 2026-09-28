from django.shortcuts import get_object_or_404

from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.catalog.models import ProductVariant

from .models import Wishlist, WishlistItem
from .serializers import (
    WishlistItemSerializer,
    WishlistSerializer,
)


class WishlistViewSet(viewsets.ViewSet):
    permission_classes = [IsAuthenticated]

    def get_wishlist(self, user):
        wishlist, _ = Wishlist.objects.get_or_create(
            user=user
        )
        return wishlist

    def list(self, request):
        wishlist = self.get_wishlist(
            request.user
        )

        wishlist = (
            Wishlist.objects
            .prefetch_related(
                "items__variant__product"
            )
            .get(pk=wishlist.pk)
        )

        serializer = WishlistSerializer(
            wishlist
        )

        return Response(serializer.data)

    @action(
        detail=False,
        methods=["post"],
        url_path="items",
    )
    def add_item(self, request):
        variant_id = request.data.get(
            "variant"
        )

        if not variant_id:
            return Response(
                {
                    "variant": (
                        "La variante est obligatoire."
                    )
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        variant = get_object_or_404(
            ProductVariant,
            pk=variant_id,
            is_active=True,
        )

        wishlist = self.get_wishlist(
            request.user
        )

        item, created = (
            WishlistItem.objects.get_or_create(
                wishlist=wishlist,
                variant=variant,
            )
        )

        serializer = WishlistItemSerializer(
            item
        )

        return Response(
            serializer.data,
            status=(
                status.HTTP_201_CREATED
                if created
                else status.HTTP_200_OK
            ),
        )

    @action(
        detail=False,
        methods=["delete"],
        url_path=r"items/(?P<item_id>\d+)",
    )
    def remove_item(
        self,
        request,
        item_id=None,
    ):
        wishlist = self.get_wishlist(
            request.user
        )

        item = get_object_or_404(
            WishlistItem,
            pk=item_id,
            wishlist=wishlist,
        )

        item.delete()

        return Response(
            status=status.HTTP_204_NO_CONTENT
        )

    @action(
        detail=False,
        methods=["delete"],
        url_path="clear",
    )
    def clear(self, request):
        wishlist = self.get_wishlist(
            request.user
        )

        wishlist.items.all().delete()

        return Response(
            {
                "message": (
                    "La wishlist a été vidée."
                )
            },
            status=status.HTTP_200_OK,
        )