from django.urls import path

from .views import WishlistViewSet


wishlist_view = WishlistViewSet.as_view({
    "get": "list",
})

add_item_view = WishlistViewSet.as_view({
    "post": "add_item",
})

remove_item_view = WishlistViewSet.as_view({
    "delete": "remove_item",
})

clear_view = WishlistViewSet.as_view({
    "delete": "clear",
})


urlpatterns = [
    path(
        "wishlist/",
        wishlist_view,
        name="wishlist",
    ),
    path(
        "wishlist/items/",
        add_item_view,
        name="wishlist-add-item",
    ),
    path(
        "wishlist/items/<int:item_id>/",
        remove_item_view,
        name="wishlist-remove-item",
    ),
    path(
        "wishlist/clear/",
        clear_view,
        name="wishlist-clear",
    ),
]