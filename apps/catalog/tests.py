from decimal import Decimal

from rest_framework.test import APITestCase

from apps.accounts.models import User
from apps.stocks.models import Stock

from .models import (
    Attribute,
    AttributeValue,
    Brand,
    Category,
    Product,
    ProductCategory,
    ProductImage,
    ProductVariant,
    VariantAttributeValue,
)


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


class ProductCatalogTestBase(APITestCase):

    def setUp(self):
        self.parent_category = Category.objects.create(
            name="Vêtements",
            slug="vetements",
        )

        self.tshirts_category = Category.objects.create(
            name="T-shirts",
            slug="t-shirts",
            parent=self.parent_category,
        )

        self.shoes_category = Category.objects.create(
            name="Chaussures",
            slug="chaussures",
        )

        self.nike = Brand.objects.create(name="Nike")
        self.adidas = Brand.objects.create(name="Adidas")

        self.color = Attribute.objects.create(name="Couleur")
        self.size = Attribute.objects.create(name="Taille")

        self.red = AttributeValue.objects.create(
            attribute=self.color,
            value="Rouge",
        )
        self.blue = AttributeValue.objects.create(
            attribute=self.color,
            value="Bleu",
        )
        self.black = AttributeValue.objects.create(
            attribute=self.color,
            value="Noir",
        )
        self.size_m = AttributeValue.objects.create(
            attribute=self.size,
            value="M",
        )
        self.size_l = AttributeValue.objects.create(
            attribute=self.size,
            value="L",
        )
        self.size_42 = AttributeValue.objects.create(
            attribute=self.size,
            value="42",
        )

        self.red_tshirt = Product.objects.create(
            brand=self.nike,
            name="T-shirt Rouge",
            slug="t-shirt-rouge",
            description="T-shirt en coton rouge",
            base_price=Decimal("5000.00"),
        )
        ProductCategory.objects.create(
            product=self.red_tshirt,
            category=self.tshirts_category,
        )

        self.red_m = ProductVariant.objects.create(
            product=self.red_tshirt,
            sku="TSHIRT-ROUGE-M",
            price=Decimal("5500.00"),
        )
        self.red_l = ProductVariant.objects.create(
            product=self.red_tshirt,
            sku="TSHIRT-ROUGE-L",
            price=Decimal("6000.00"),
        )

        VariantAttributeValue.objects.create(
            variant=self.red_m,
            attribute_value=self.red,
        )
        VariantAttributeValue.objects.create(
            variant=self.red_m,
            attribute_value=self.size_m,
        )
        VariantAttributeValue.objects.create(
            variant=self.red_l,
            attribute_value=self.red,
        )
        VariantAttributeValue.objects.create(
            variant=self.red_l,
            attribute_value=self.size_l,
        )

        Stock.objects.create(
            variant=self.red_m,
            quantity=5,
            reserved_quantity=0,
        )
        Stock.objects.create(
            variant=self.red_l,
            quantity=2,
            reserved_quantity=2,
        )

        ProductImage.objects.create(
            product=self.red_tshirt,
            image_url="https://example.com/rouge-secondaire.jpg",
            is_primary=False,
        )
        ProductImage.objects.create(
            product=self.red_tshirt,
            image_url="https://example.com/rouge-principale.jpg",
            alt_text="T-shirt rouge",
            is_primary=True,
        )

        self.runner = Product.objects.create(
            brand=self.adidas,
            name="Chaussure Runner",
            slug="chaussure-runner",
            description="Chaussure de running",
            base_price=Decimal("12000.00"),
        )
        ProductCategory.objects.create(
            product=self.runner,
            category=self.shoes_category,
        )

        self.runner_variant = ProductVariant.objects.create(
            product=self.runner,
            sku="RUNNER-NOIR-42",
            price=Decimal("12000.00"),
        )
        VariantAttributeValue.objects.create(
            variant=self.runner_variant,
            attribute_value=self.black,
        )
        VariantAttributeValue.objects.create(
            variant=self.runner_variant,
            attribute_value=self.size_42,
        )
        Stock.objects.create(
            variant=self.runner_variant,
            quantity=3,
            reserved_quantity=0,
        )

        self.blue_tshirt = Product.objects.create(
            brand=self.nike,
            name="T-shirt Bleu",
            slug="t-shirt-bleu",
            description="T-shirt en coton bleu",
            base_price=Decimal("4500.00"),
        )
        ProductCategory.objects.create(
            product=self.blue_tshirt,
            category=self.tshirts_category,
        )

        self.blue_m = ProductVariant.objects.create(
            product=self.blue_tshirt,
            sku="TSHIRT-BLEU-M",
            price=Decimal("4500.00"),
        )
        VariantAttributeValue.objects.create(
            variant=self.blue_m,
            attribute_value=self.blue,
        )
        VariantAttributeValue.objects.create(
            variant=self.blue_m,
            attribute_value=self.size_m,
        )
        Stock.objects.create(
            variant=self.blue_m,
            quantity=0,
            reserved_quantity=0,
        )

        self.inactive_product = Product.objects.create(
            brand=self.nike,
            name="Produit caché",
            slug="produit-cache",
            base_price=Decimal("1000.00"),
            is_active=False,
        )
        ProductCategory.objects.create(
            product=self.inactive_product,
            category=self.tshirts_category,
        )

        self.accessory = Product.objects.create(
            brand=self.nike,
            name="Accessoire",
            slug="accessoire",
            base_price=Decimal("3000.00"),
        )

        self.admin_user = User.objects.create_superuser(
            email="catalog-admin@example.com",
            password="TestPassword123!",
            first_name="Admin",
            last_name="Catalogue",
        )

    def product_ids(self, query=""):
        response = self.client.get(
            f"/api/products/{query}"
        )

        self.assertEqual(response.status_code, 200)

        return {
            item["id"]
            for item in response.data["results"]
        }


class ProductSearchAndFilterTests(ProductCatalogTestBase):

    def test_search_by_name_sku_brand_and_category(self):
        self.assertEqual(
            self.product_ids("?search=Chaussure"),
            {self.runner.id},
        )

        self.assertEqual(
            self.product_ids("?search=RUNNER-NOIR-42"),
            {self.runner.id},
        )

        self.assertEqual(
            self.product_ids("?search=Adidas"),
            {self.runner.id},
        )

        self.assertEqual(
            self.product_ids("?search=T-shirts"),
            {self.red_tshirt.id, self.blue_tshirt.id},
        )

        self.assertEqual(
            self.product_ids("?search=Produit caché"),
            set(),
        )

    def test_filter_by_category_includes_subcategories(self):
        self.assertEqual(
            self.product_ids(
                f"?category={self.parent_category.id}"
            ),
            {self.red_tshirt.id, self.blue_tshirt.id},
        )

        self.assertEqual(
            self.product_ids(
                f"?category={self.tshirts_category.id}"
            ),
            {self.red_tshirt.id, self.blue_tshirt.id},
        )

        self.assertEqual(
            self.product_ids("?category=999999"),
            set(),
        )

    def test_filter_by_brand(self):
        self.assertEqual(
            self.product_ids(f"?brand={self.nike.id}"),
            {
                self.red_tshirt.id,
                self.blue_tshirt.id,
                self.accessory.id,
            },
        )

        self.assertEqual(
            self.product_ids(f"?brand={self.adidas.id}"),
            {self.runner.id},
        )

    def test_filter_by_price_range(self):
        self.assertEqual(
            self.product_ids(
                "?price_min=4000&price_max=6000"
            ),
            {
                self.red_tshirt.id,
                self.blue_tshirt.id,
            },
        )

        self.assertEqual(
            self.product_ids("?price_max=3000"),
            {self.accessory.id},
        )

    def test_filter_by_stock_availability(self):
        self.assertEqual(
            self.product_ids("?in_stock=true"),
            {
                self.red_tshirt.id,
                self.runner.id,
            },
        )

        self.assertEqual(
            self.product_ids("?in_stock=false"),
            {
                self.blue_tshirt.id,
                self.accessory.id,
            },
        )

    def test_filter_by_attributes(self):
        self.assertEqual(
            self.product_ids(
                (
                    "?attributes="
                    f"{self.red.id},{self.size_m.id}"
                )
            ),
            {self.red_tshirt.id},
        )

        self.assertEqual(
            self.product_ids(
                "?attributes=Couleur:Rouge,Taille:M"
            ),
            {self.red_tshirt.id},
        )

        self.assertEqual(
            self.product_ids(
                f"?attributes={self.black.id}"
            ),
            {self.runner.id},
        )

        response = self.client.get(
            "/api/products/?attributes=Inconnu:Valeur"
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["results"], [])

    def test_ordering_by_price_and_newest(self):
        response = self.client.get(
            "/api/products/?ordering=price"
        )

        self.assertEqual(response.status_code, 200)

        ids = [item["id"] for item in response.data["results"]]

        self.assertEqual(
            ids,
            [
                self.accessory.id,
                self.blue_tshirt.id,
                self.red_tshirt.id,
                self.runner.id,
            ],
        )

        response = self.client.get(
            "/api/products/?ordering=-price"
        )

        self.assertEqual(response.status_code, 200)

        ids = [item["id"] for item in response.data["results"]]

        self.assertEqual(
            ids,
            [
                self.runner.id,
                self.red_tshirt.id,
                self.blue_tshirt.id,
                self.accessory.id,
            ],
        )

        response = self.client.get(
            "/api/products/?ordering=newest"
        )

        self.assertEqual(response.status_code, 200)

        self.assertEqual(
            response.data["results"][0]["id"],
            self.accessory.id,
        )

    def test_pagination_size_is_configurable(self):
        response = self.client.get(
            "/api/products/?page_size=2"
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["count"], 4)
        self.assertEqual(len(response.data["results"]), 2)
        self.assertIsNotNone(response.data["next"])

        response = self.client.get(
            "/api/products/?page_size=2&page=2"
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data["results"]), 2)
        self.assertIsNone(response.data["next"])


class ProductRepresentationTests(ProductCatalogTestBase):

    def test_product_list_exposes_summary_data(self):
        response = self.client.get("/api/products/")

        self.assertEqual(response.status_code, 200)

        products = {
            item["id"]: item
            for item in response.data["results"]
        }

        red_tshirt = products[self.red_tshirt.id]

        self.assertEqual(red_tshirt["brand"]["name"], "Nike")
        self.assertEqual(
            [
                category["slug"]
                for category in red_tshirt["categories"]
            ],
            ["t-shirts"],
        )
        self.assertEqual(
            red_tshirt["primary_image"]["image_url"],
            "https://example.com/rouge-principale.jpg",
        )
        self.assertEqual(
            Decimal(red_tshirt["price_min"]),
            Decimal("5500.00"),
        )
        self.assertEqual(
            Decimal(red_tshirt["price_max"]),
            Decimal("6000.00"),
        )
        self.assertTrue(red_tshirt["in_stock"])

        accessory = products[self.accessory.id]

        self.assertEqual(
            Decimal(accessory["price_min"]),
            Decimal("3000.00"),
        )
        self.assertFalse(accessory["in_stock"])
        self.assertIsNone(accessory["primary_image"])

    def test_product_detail_includes_nested_catalog_data(self):
        response = self.client.get(
            f"/api/products/{self.red_tshirt.id}/"
        )

        self.assertEqual(response.status_code, 200)

        data = response.data

        self.assertEqual(data["brand"]["name"], "Nike")
        self.assertEqual(
            [
                category["slug"]
                for category in data["categories"]
            ],
            ["t-shirts"],
        )
        self.assertEqual(
            Decimal(data["price_min"]),
            Decimal("5500.00"),
        )
        self.assertEqual(
            Decimal(data["price_max"]),
            Decimal("6000.00"),
        )
        self.assertTrue(data["in_stock"])

        self.assertEqual(len(data["images"]), 2)
        self.assertTrue(
            any(
                image["is_primary"]
                for image in data["images"]
            )
        )

        variants = {
            variant["sku"]: variant
            for variant in data["variants"]
        }

        self.assertEqual(len(variants), 2)

        red_m = variants["TSHIRT-ROUGE-M"]

        self.assertEqual(
            {
                attribute["value"]
                for attribute in red_m["attributes"]
            },
            {"Rouge", "M"},
        )
        self.assertEqual(
            red_m["stock"]["available_quantity"],
            5,
        )
        self.assertTrue(red_m["stock"]["in_stock"])

        red_l = variants["TSHIRT-ROUGE-L"]

        self.assertEqual(
            red_l["stock"]["available_quantity"],
            0,
        )
        self.assertFalse(red_l["stock"]["in_stock"])

    def test_anonymous_cannot_retrieve_inactive_product(self):
        response = self.client.get(
            f"/api/products/{self.inactive_product.id}/"
        )

        self.assertEqual(response.status_code, 404)


class ProductWriteTests(ProductCatalogTestBase):

    def test_create_product_generates_slug(self):
        self.client.force_authenticate(self.admin_user)

        response = self.client.post(
            "/api/products/",
            {
                "name": "Nouveau Produit Été",
                "base_price": "2500.00",
                "categories": [self.tshirts_category.id],
            },
            format="json",
        )

        self.assertEqual(response.status_code, 201)
        self.assertEqual(
            response.data["slug"],
            "nouveau-produit-ete",
        )

        product = Product.objects.get(
            slug="nouveau-produit-ete"
        )

        self.assertTrue(
            product.product_categories.filter(
                category=self.tshirts_category
            ).exists()
        )

    def test_create_product_rejects_duplicate_generated_slug(self):
        count = Product.objects.count()

        self.client.force_authenticate(self.admin_user)

        response = self.client.post(
            "/api/products/",
            {
                "name": "T-shirt Rouge",
                "base_price": "2500.00",
            },
            format="json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("slug", response.data)
        self.assertEqual(Product.objects.count(), count)


class CatalogAuxiliaryFilterTests(ProductCatalogTestBase):

    def test_category_parent_and_search_filters(self):
        response = self.client.get(
            "/api/categories/?parent=root"
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            {
                category["slug"]
                for category in response.data["results"]
            },
            {"vetements", "chaussures"},
        )

        response = self.client.get(
            f"/api/categories/?parent={self.parent_category.id}"
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            [
                category["slug"]
                for category in response.data["results"]
            ],
            ["t-shirts"],
        )

        response = self.client.get(
            "/api/categories/?search=chauss"
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            [
                category["slug"]
                for category in response.data["results"]
            ],
            ["chaussures"],
        )

    def test_brand_search_filter(self):
        response = self.client.get(
            "/api/brands/?search=nike"
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            [
                brand["name"]
                for brand in response.data["results"]
            ],
            ["Nike"],
        )

    def test_product_image_filter(self):
        response = self.client.get(
            f"/api/product-images/?product={self.red_tshirt.id}"
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["count"], 2)

        response = self.client.get(
            f"/api/product-images/?product={self.inactive_product.id}"
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["count"], 0)

    def test_product_variant_filter(self):
        response = self.client.get(
            (
                f"/api/product-variants/?product={self.red_tshirt.id}"
                "&search=ROUGE"
            )
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            {
                variant["sku"]
                for variant in response.data["results"]
            },
            {"TSHIRT-ROUGE-M", "TSHIRT-ROUGE-L"},
        )

        response = self.client.get(
            "/api/product-variants/?product=999999"
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["count"], 0)

    def test_attribute_and_attribute_value_filters(self):
        response = self.client.get(
            "/api/attributes/?search=coul"
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            [
                attribute["name"]
                for attribute in response.data["results"]
            ],
            ["Couleur"],
        )

        response = self.client.get(
            f"/api/attribute-values/?attribute={self.color.id}"
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            {
                value["value"]
                for value in response.data["results"]
            },
            {"Rouge", "Bleu", "Noir"},
        )

    def test_variant_attribute_value_filter(self):
        response = self.client.get(
            (
                "/api/variant-attribute-values/"
                f"?variant={self.red_m.id}"
            )
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["count"], 2)
