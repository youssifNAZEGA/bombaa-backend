from django.urls import path

from rest_framework_simplejwt.views import TokenRefreshView

from .views import (
    LoginView,
    RegisterView,
    me_view,
    profile_view,
    change_password_view,
    logout_view,
    test_products_view,
    test_products_create,
)


urlpatterns = [

    path(
        "register/",
        RegisterView.as_view(),
        name="register",
    ),

    path(
        "login/",
        LoginView.as_view(),
        name="login",
    ),

    path(
        "refresh/",
        TokenRefreshView.as_view(),
        name="token_refresh",
    ),


    path(
        "me/",
        me_view,
        name="me",
    ),

    path(
        "profile/",
        profile_view,
        name="profile"
    ),

    path(
        "change-password/",
        change_password_view,
        name="change-password",
    ),

    path(
        "logout/",
        logout_view,
        name="logout",
    ),

    path(
        "test/products/",
        test_products_view,
        name="test-products-view",
    ),

    path(
        "test/products/create/",
        test_products_create,
        name="test-products-create",
    ),
]