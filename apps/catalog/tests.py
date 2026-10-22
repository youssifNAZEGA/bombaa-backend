from decimal import Decimal

from rest_framework.test import APITestCase

from .models import Brand, Category, Product


class PublicCatalogTests(APITestCase):

    def setUp(self):
        self.category = Category.objects.create(
            name="Catégorie publique",
            slug="categorie-publique",
        )

        self.brand = Brand.objects.create(
            name="Marque publique",
        )

        self.active_product = Product.objects.create(
            brand=self.brand,
            name="Produit actif",
            slug="produit-actif",
            base_price=Decimal("5000.00"),
            is_active=True,
        )

        self.inactive_product = Product.objects.create(
            brand=self.brand,
            name="Produit inactif",
            slug="produit-inactif",
            base_price=Decimal("7000.00"),
            is_active=False,
        )

    def test_anonymous_can_list_categories(self):
        response = self.client.get("/api/categories/")

        self.assertEqual(response.status_code, 200)

    def test_anonymous_can_list_brands(self):
        response = self.client.get("/api/brands/")

        self.assertEqual(response.status_code, 200)

    def test_anonymous_can_list_products(self):
        response = self.client.get("/api/products/")

        self.assertEqual(response.status_code, 200)

        names = [
            item["name"]
            for item in response.data["results"]
        ]

        self.assertIn(self.active_product.name, names)
        self.assertNotIn(self.inactive_product.name, names)

    def test_anonymous_cannot_create_product(self):
        response = self.client.post(
            "/api/products/",
            {
                "name": "Produit pirate",
                "slug": "produit-pirate",
                "base_price": "1000.00",
            },
            format="json",
        )

        self.assertIn(response.status_code, [401, 403])
        self.assertFalse(
            Product.objects.filter(slug="produit-pirate").exists()
        )
