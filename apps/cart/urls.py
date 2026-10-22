from django.urls import path

from .views import CartViewSet


cart_view = CartViewSet.as_view({
    "get": "list",
})

add_item_view = CartViewSet.as_view({
    "post": "add_item",
})

item_detail_view = CartViewSet.as_view({
    "patch": "update_item",
    "delete": "remove_item",
})

clear_cart_view = CartViewSet.as_view({
    "delete": "clear",
})


urlpatterns = [
    path(
        "cart/",
        cart_view,
        name="cart",
    ),
    path(
        "cart/items/",
        add_item_view,
        name="cart-add-item",
    ),
    path(
        "cart/items/<int:item_id>/",
        item_detail_view,
        name="cart-item-detail",
    ),
    path(
        "cart/clear/",
        clear_cart_view,
        name="cart-clear",
    ),
]