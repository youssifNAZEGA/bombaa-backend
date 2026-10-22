from django.urls import path

from .views import OrderViewSet


order_list_view = OrderViewSet.as_view({
    "get": "list",
    "post": "create",
})

order_detail_view = OrderViewSet.as_view({
    "get": "retrieve",
})

order_cancel_view = OrderViewSet.as_view({
    "post": "cancel",
})

order_status_view = OrderViewSet.as_view({
    "patch": "update_status",
})


urlpatterns = [
    path(
        "orders/",
        order_list_view,
        name="order-list",
    ),
    path(
        "orders/<int:pk>/",
        order_detail_view,
        name="order-detail",
    ),
    path(
        "orders/<int:pk>/cancel/",
        order_cancel_view,
        name="order-cancel",
    ),
    path(
        "orders/<int:pk>/status/",
        order_status_view,
        name="order-status",
    ),
]