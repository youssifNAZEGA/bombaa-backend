from decimal import Decimal

from rest_framework.test import APITestCase

from apps.accounts.models import User
from apps.catalog.models import Product, ProductVariant

from .models import Cart, CartItem


class CartItemEndpointsTests(APITestCase):

    def setUp(self):
        self.user = User.objects.create_user(
            email="cart-test@example.com",
            password="TestPassword123!",
            first_name="Cart",
            last_name="Test",
        )

        self.client.force_authenticate(self.user)

        self.product = Product.objects.create(
            name="Produit panier",
            slug="produit-panier",
            base_price=Decimal("5000.00"),
        )

        self.variant = ProductVariant.objects.create(
            product=self.product,
            sku="CART-001",
            price=Decimal("5000.00"),
        )

        self.cart = Cart.objects.create(user=self.user)

        self.item = CartItem.objects.create(
            cart=self.cart,
            variant=self.variant,
            quantity=2,
        )

    def test_delete_cart_item(self):
        response = self.client.delete(
            f"/api/cart/items/{self.item.id}/"
        )

        self.assertEqual(response.status_code, 204)
        self.assertFalse(
            CartItem.objects.filter(pk=self.item.pk).exists()
        )

    def test_patch_cart_item_quantity(self):
        response = self.client.patch(
            f"/api/cart/items/{self.item.id}/",
            {"quantity": 5},
            format="json",
        )

        self.assertEqual(response.status_code, 200)

        self.item.refresh_from_db()
        self.assertEqual(self.item.quantity, 5)

    def test_cannot_delete_another_user_cart_item(self):
        other_user = User.objects.create_user(
            email="other-cart@example.com",
            password="TestPassword123!",
            first_name="Other",
            last_name="Client",
        )

        other_cart = Cart.objects.create(user=other_user)

        other_item = CartItem.objects.create(
            cart=other_cart,
            variant=self.variant,
            quantity=1,
        )

        response = self.client.delete(
            f"/api/cart/items/{other_item.id}/"
        )

        self.assertEqual(response.status_code, 404)
        self.assertTrue(
            CartItem.objects.filter(pk=other_item.pk).exists()
        )
