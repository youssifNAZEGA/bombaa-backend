from django.urls import path

from .views import CartViewSet


cart_view = CartViewSet.as_view({
    "get": "list",
})

add_item_view = CartViewSet.as_view({
    "post": "add_item",
})

update_item_view = CartViewSet.as_view({
    "patch": "update_item",
})

remove_item_view = CartViewSet.as_view({
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
        update_item_view,
        name="cart-update-item",
    ),
    path(
        "cart/items/<int:item_id>/",
        remove_item_view,
        name="cart-remove-item",
    ),
    path(
        "cart/clear/",
        clear_cart_view,
        name="cart-clear",
    ),
]