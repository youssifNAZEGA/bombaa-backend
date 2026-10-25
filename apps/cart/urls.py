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

coupon_view = CartViewSet.as_view({
    "post": "apply_coupon",
    "delete": "remove_coupon",
})

apply_coupon_view = CartViewSet.as_view({
    "post": "apply_coupon",
})

remove_coupon_view = CartViewSet.as_view({
    "delete": "remove_coupon",
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
        "cart/coupon/",
        coupon_view,
        name="cart-coupon",
    ),
    path(
        "cart/apply-coupon/",
        apply_coupon_view,
        name="cart-apply-coupon",
    ),
    path(
        "cart/remove-coupon/",
        remove_coupon_view,
        name="cart-remove-coupon",
    ),
    path(
        "cart/clear/",
        clear_cart_view,
        name="cart-clear",
    ),
]