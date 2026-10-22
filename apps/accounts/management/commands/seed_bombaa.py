
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone
from apps.stocks.models import Stock, StockMovement
from apps.accounts.models import User, Role
from apps.addresses.models import Address
from apps.catalog.models import (
    Category,
    Brand,
    Product,
    ProductCategory,
    ProductImage,
    Attribute,
    AttributeValue,
    ProductVariant,
    VariantAttributeValue,
    
)
from apps.payments.models import PaymentMethod, Payment,Transaction
from apps.cart.models import Cart, CartItem
from apps.wishlist.models import Wishlist, WishlistItem
from apps.orders.models import Order, OrderAddress, OrderItem
from decimal import Decimal

class Command(BaseCommand):
    help = "Peuple la base de données BOMBAA avec les données de développement."

    @transaction.atomic
    def handle(self, *args, **options):

        self.stdout.write(
            self.style.MIGRATE_HEADING(
                "=== SEED BOMBAA ==="
            )
        )

        self.seed_users()
        self.seed_catalog()
        self.seed_payment_methods()
        self.seed_products()
        self.seed_stocks()
        self.seed_addresses()
        self.seed_carts()
        self.seed_wishlists()
        self.seed_orders()
        self.seed_payments()


        self.stdout.write(
            self.style.SUCCESS(
                "\n✓ Peuplement BOMBAA terminé avec succès."
            )
        )

    # ==========================================================
    # USERS
    # ==========================================================

    def seed_users(self):

        admin_role = Role.objects.get(
            name="ADMIN"
        )

        client_role = Role.objects.get(
            name="CLIENT"
        )

        admin, created = User.objects.get_or_create(
            email="admin@bombaa.com",
            defaults={
                "first_name": "Admin",
                "last_name": "BOMBAA",
                "phone": "+22890000001",
                "is_active": True,
                "is_staff": True,
                "is_superuser": True,
            },
        )

        if created:
            admin.set_password("Admin12345!")
            admin.save()

        admin.roles.add(admin_role)

        self.stdout.write(
            self.style.SUCCESS(
                "✓ Administrateur : admin@bombaa.com"
            )
        )

        clients = [
            {
                "email": "client1@bombaa.com",
                "first_name": "Koffi",
                "last_name": "Mensah",
                "phone": "+22890000002",
            },
            {
                "email": "client2@bombaa.com",
                "first_name": "Ama",
                "last_name": "Kossi",
                "phone": "+22890000003",
            },
            {
                "email": "client3@bombaa.com",
                "first_name": "Yao",
                "last_name": "Adjei",
                "phone": "+22890000004",
            },
        ]

        for data in clients:

            user, created = User.objects.get_or_create(
                email=data["email"],
                defaults={
                    "first_name": data["first_name"],
                    "last_name": data["last_name"],
                    "phone": data["phone"],
                    "is_active": True,
                },
            )

            if created:
                user.set_password(
                    "Client12345!"
                )
                user.save()

            user.roles.add(client_role)

            self.stdout.write(
                f"  → {user.email}"
            )



    def seed_addresses(self):
        addresses = [
            {
                "email": "client1@bombaa.com",
                "label": "Maison",
                "first_name": "Koffi",
                "last_name": "Mensah",
                "phone": "+22890000002",
                "address_line_1": "12 Rue des Cocotiers",
                "address_line_2": "",
                "city": "Lomé",
                "state": "Golfe",
                "postal_code": "01 BP 1234",
                "country": "Togo",
                "is_default": True,
            },
            {
                "email": "client1@bombaa.com",
                "label": "Bureau",
                "first_name": "Koffi",
                "last_name": "Mensah",
                "phone": "+22890000002",
                "address_line_1": "45 Boulevard du 30 Août",
                "address_line_2": "",
                "city": "Lomé",
                "state": "Golfe",
                "postal_code": "01 BP 5678",
                "country": "Togo",
                "is_default": False,
            },

            {
                "email": "client2@bombaa.com",
                "label": "Maison",
                "first_name": "Ama",
                "last_name": "Kossi",
                "phone": "+22890000003",
                "address_line_1": "18 Rue de la Paix",
                "address_line_2": "",
                "city": "Lomé",
                "state": "Golfe",
                "postal_code": "01 BP 2345",
                "country": "Togo",
                "is_default": True,
            },
            {
                "email": "client2@bombaa.com",
                "label": "Travail",
                "first_name": "Ama",
                "last_name": "Kossi",
                "phone": "+22890000003",
                "address_line_1": "10 Avenue de la Libération",
                "address_line_2": "",
                "city": "Lomé",
                "state": "Golfe",
                "postal_code": "01 BP 6789",
                "country": "Togo",
                "is_default": False,
            },

            {
                "email": "client3@bombaa.com",
                "label": "Maison",
                "first_name": "Yao",
                "last_name": "Adjei",
                "phone": "+22890000004",
                "address_line_1": "7 Rue de la Marina",
                "address_line_2": "",
                "city": "Lomé",
                "state": "Golfe",
                "postal_code": "01 BP 3456",
                "country": "Togo",
                "is_default": True,
            },
            {
                "email": "client3@bombaa.com",
                "label": "Famille",
                "first_name": "Yao",
                "last_name": "Adjei",
                "phone": "+22890000004",
                "address_line_1": "25 Route de Baguida",
                "address_line_2": "",
                "city": "Lomé",
                "state": "Golfe",
                "postal_code": "01 BP 7890",
                "country": "Togo",
                "is_default": False,
            },
        ]

        for data in addresses:
            user = User.objects.get(email=data["email"])

            # On cherche une adresse existante avec le même label
            address = Address.objects.filter(
                user=user,
                label=data["label"],
            ).first()

            if address:
                for field, value in data.items():
                    if field != "email":
                        setattr(address, field, value)

                address.save()
            else:
                Address.objects.create(
                    user=user,
                    label=data["label"],
                    first_name=data["first_name"],
                    last_name=data["last_name"],
                    phone=data["phone"],
                    address_line_1=data["address_line_1"],
                    address_line_2=data["address_line_2"],
                    city=data["city"],
                    state=data["state"],
                    postal_code=data["postal_code"],
                    country=data["country"],
                    is_default=data["is_default"],
                )

        # Sécurité : une seule adresse par client est définie comme principale
        for email in [
            "client1@bombaa.com",
            "client2@bombaa.com",
            "client3@bombaa.com",
        ]:
            user = User.objects.get(email=email)

            default_addresses = Address.objects.filter(
                user=user,
                is_default=True,
            ).order_by("created_at")

            if default_addresses.exists():
                first_default = default_addresses.first()

                Address.objects.filter(
                    user=user,
                    is_default=True,
                ).exclude(
                    id=first_default.id
                ).update(is_default=False)

        self.stdout.write(
            self.style.SUCCESS("Adresses de test créées/mises à jour.")
        )

    # ==========================================================
    # CATALOG
    # ==========================================================

    def seed_catalog(self):

        categories = [
            {
                "name": "Vêtements",
                "slug": "vetements",
                "description": "Vêtements pour hommes et femmes.",
            },
            {
                "name": "Chaussures",
                "slug": "chaussures",
                "description": "Chaussures et baskets.",
            },
            {
                "name": "Accessoires",
                "slug": "accessoires",
                "description": "Accessoires de mode.",
            },
            {
                "name": "Électronique",
                "slug": "electronique",
                "description": "Produits électroniques.",
            },
            {
                "name": "Beauté",
                "slug": "beaute",
                "description": "Produits de beauté.",
            },
            {
                "name": "Maison",
                "slug": "maison",
                "description": "Produits pour la maison.",
            },
        ]

        for data in categories:

            category, _ = Category.objects.update_or_create(
                slug=data["slug"],
                defaults={
                    "name": data["name"],
                    "description": data["description"],
                    "is_active": True,
                },
            )

            self.stdout.write(
                f"  → Catégorie : {category.name}"
            )

        brands = [
            {
                "name": "BOMBAA",
                "description": "Marque officielle BOMBAA.",
            },
            {
                "name": "Nike",
                "description": "Articles de sport et de mode.",
            },
            {
                "name": "Adidas",
                "description": "Articles de sport et de mode.",
            },
            {
                "name": "Samsung",
                "description": "Produits électroniques.",
            },
        ]

        for data in brands:

            brand, _ = Brand.objects.update_or_create(
                name=data["name"],
                defaults={
                    "description": data["description"],
                    "is_active": True,
                },
            )

            self.stdout.write(
                f"  → Marque : {brand.name}"
            )

        attributes = {
            "Couleur": [
                "Noir",
                "Blanc",
                "Rouge",
                "Bleu",
                "Vert",
            ],
            "Taille": [
                "XS",
                "S",
                "M",
                "L",
                "XL",
                "XXL",
            ],
            "Pointure": [
                "38",
                "39",
                "40",
                "41",
                "42",
                "43",
                "44",
            ],
            "Matière": [
                "Coton",
                "Polyester",
                "Cuir",
                "Denim",
            ],
            "Capacité": [
                "64 Go",
                "128 Go",
                "256 Go",
                "512 Go",
            ],
        }

        for attribute_name, values in attributes.items():

            attribute, _ = Attribute.objects.update_or_create(
                name=attribute_name
            )

            for value in values:

                AttributeValue.objects.update_or_create(
                    attribute=attribute,
                    value=value,
                )

            self.stdout.write(
                f"  → Attribut : {attribute_name}"
            )

    # ==========================================================
    # PAYMENT METHODS
    # ==========================================================

    def seed_payment_methods(self):

        methods = [
            {
                "name": "Mobile Money",
                "code": "MOBILE_MONEY",
                "description": (
                    "Paiement par services Mobile Money."
                ),
            },
            {
                "name": "Carte bancaire",
                "code": "CARD",
                "description": (
                    "Paiement par carte bancaire."
                ),
            },
            {
                "name": "Virement bancaire",
                "code": "BANK_TRANSFER",
                "description": (
                    "Paiement par virement bancaire."
                ),
            },
            {
                "name": "Paiement à la livraison",
                "code": "CASH_ON_DELIVERY",
                "description": (
                    "Paiement à la livraison."
                ),
            },
        ]

        for data in methods:

            method, _ = PaymentMethod.objects.update_or_create(
                code=data["code"],
                defaults={
                    "name": data["name"],
                    "description": data["description"],
                    "is_active": True,
                },
            )

            self.stdout.write(
                f"  → Paiement : {method.name}"
            )



    # ==========================================================
    # PRODUCTS / VARIANTS
    # ==========================================================

    def seed_products(self):

        categories = {
            category.slug: category
            for category in Category.objects.all()
        }

        brands = {
            brand.name: brand
            for brand in Brand.objects.all()
        }

        attributes = {
            attribute.name: attribute
            for attribute in Attribute.objects.prefetch_related("values")
        }

        def get_attribute_value(attribute_name, value):
            attribute = attributes[attribute_name]

            return AttributeValue.objects.get(
                attribute=attribute,
                value=value,
            )

        products = [
            {
                "name": "T-shirt BOMBAA Classic",
                "slug": "t-shirt-bombaa-classic",
                "description": (
                    "T-shirt BOMBAA confortable et polyvalent "
                    "pour un usage quotidien."
                ),
                "base_price": "8500.00",
                "brand": "BOMBAA",
                "categories": ["vetements"],
                "images": [
                    (
                        "https://example.com/products/"
                        "tshirt-bombaa-classic-noir.jpg",
                        "T-shirt BOMBAA Classic noir",
                        True,
                    ),
                    (
                        "https://example.com/products/"
                        "tshirt-bombaa-classic-blanc.jpg",
                        "T-shirt BOMBAA Classic blanc",
                        False,
                    ),
                ],
                "variants": [
                    {
                        "sku": "BOMBAA-TSH-NOIR-M",
                        "price": "8500.00",
                        "attributes": {
                            "Couleur": "Noir",
                            "Taille": "M",
                        },
                    },
                    {
                        "sku": "BOMBAA-TSH-NOIR-L",
                        "price": "8500.00",
                        "attributes": {
                            "Couleur": "Noir",
                            "Taille": "L",
                        },
                    },
                    {
                        "sku": "BOMBAA-TSH-BLANC-M",
                        "price": "8500.00",
                        "attributes": {
                            "Couleur": "Blanc",
                            "Taille": "M",
                        },
                    },
                ],
            },
            {
                "name": "Jean BOMBAA Premium",
                "slug": "jean-bombaa-premium",
                "description": (
                    "Jean BOMBAA premium avec une coupe moderne "
                    "et confortable."
                ),
                "base_price": "18000.00",
                "brand": "BOMBAA",
                "categories": ["vetements"],
                "images": [
                    (
                        "https://example.com/products/"
                        "jean-bombaa-premium.jpg",
                        "Jean BOMBAA Premium",
                        True,
                    ),
                ],
                "variants": [
                    {
                        "sku": "BOMBAA-JEAN-BLEU-40",
                        "price": "18000.00",
                        "attributes": {
                            "Couleur": "Bleu",
                            "Taille": "M",
                        },
                    },
                    {
                        "sku": "BOMBAA-JEAN-BLEU-42",
                        "price": "18000.00",
                        "attributes": {
                            "Couleur": "Bleu",
                            "Taille": "L",
                        },
                    },
                ],
            },
            {
                "name": "Nike Air Max",
                "slug": "nike-air-max",
                "description": (
                    "Chaussures Nike Air Max pour un style "
                    "sportif et moderne."
                ),
                "base_price": "65000.00",
                "brand": "Nike",
                "categories": ["chaussures"],
                "images": [
                    (
                        "https://example.com/products/"
                        "nike-air-max-noir.jpg",
                        "Nike Air Max noir",
                        True,
                    ),
                    (
                        "https://example.com/products/"
                        "nike-air-max-blanc.jpg",
                        "Nike Air Max blanc",
                        False,
                    ),
                ],
                "variants": [
                    {
                        "sku": "NIKE-AIRMAX-NOIR-42",
                        "price": "65000.00",
                        "attributes": {
                            "Couleur": "Noir",
                            "Pointure": "42",
                        },
                    },
                    {
                        "sku": "NIKE-AIRMAX-BLANC-43",
                        "price": "65000.00",
                        "attributes": {
                            "Couleur": "Blanc",
                            "Pointure": "43",
                        },
                    },
                ],
            },
            {
                "name": "Adidas Superstar",
                "slug": "adidas-superstar",
                "description": (
                    "Adidas Superstar classique adaptée "
                    "à un usage quotidien."
                ),
                "base_price": "55000.00",
                "brand": "Adidas",
                "categories": ["chaussures"],
                "images": [
                    (
                        "https://example.com/products/"
                        "adidas-superstar.jpg",
                        "Adidas Superstar",
                        True,
                    ),
                ],
                "variants": [
                    {
                        "sku": "ADIDAS-SUPERSTAR-BLANC-41",
                        "price": "55000.00",
                        "attributes": {
                            "Couleur": "Blanc",
                            "Pointure": "41",
                        },
                    },
                    {
                        "sku": "ADIDAS-SUPERSTAR-NOIR-42",
                        "price": "55000.00",
                        "attributes": {
                            "Couleur": "Noir",
                            "Pointure": "42",
                        },
                    },
                ],
            },
            {
                "name": "Sac BOMBAA Urban",
                "slug": "sac-bombaa-urban",
                "description": (
                    "Sac BOMBAA Urban pratique pour "
                    "les déplacements quotidiens."
                ),
                "base_price": "22000.00",
                "brand": "BOMBAA",
                "categories": ["accessoires"],
                "images": [
                    (
                        "https://example.com/products/"
                        "sac-bombaa-urban.jpg",
                        "Sac BOMBAA Urban",
                        True,
                    ),
                ],
                "variants": [
                    {
                        "sku": "BOMBAA-SAC-NOIR",
                        "price": "22000.00",
                        "attributes": {
                            "Couleur": "Noir",
                            "Matière": "Cuir",
                        },
                    },
                    {
                        "sku": "BOMBAA-SAC-BLEU",
                        "price": "22000.00",
                        "attributes": {
                            "Couleur": "Bleu",
                            "Matière": "Cuir",
                        },
                    },
                ],
            },
            {
                "name": "Samsung Galaxy 128 Go",
                "slug": "samsung-galaxy-128-go",
                "description": (
                    "Smartphone Samsung Galaxy avec "
                    "128 Go de stockage."
                ),
                "base_price": "175000.00",
                "brand": "Samsung",
                "categories": ["electronique"],
                "images": [
                    (
                        "https://example.com/products/"
                        "samsung-galaxy-128.jpg",
                        "Samsung Galaxy 128 Go",
                        True,
                    ),
                ],
                "variants": [
                    {
                        "sku": "SAMSUNG-GALAXY-128-NOIR",
                        "price": "175000.00",
                        "attributes": {
                            "Couleur": "Noir",
                            "Capacité": "128 Go",
                        },
                    },
                    {
                        "sku": "SAMSUNG-GALAXY-128-BLANC",
                        "price": "175000.00",
                        "attributes": {
                            "Couleur": "Blanc",
                            "Capacité": "128 Go",
                        },
                    },
                ],
            },
            {
                "name": "Samsung Galaxy 256 Go",
                "slug": "samsung-galaxy-256-go",
                "description": (
                    "Smartphone Samsung Galaxy avec "
                    "256 Go de stockage."
                ),
                "base_price": "210000.00",
                "brand": "Samsung",
                "categories": ["electronique"],
                "images": [
                    (
                        "https://example.com/products/"
                        "samsung-galaxy-256.jpg",
                        "Samsung Galaxy 256 Go",
                        True,
                    ),
                ],
                "variants": [
                    {
                        "sku": "SAMSUNG-GALAXY-256-NOIR",
                        "price": "210000.00",
                        "attributes": {
                            "Couleur": "Noir",
                            "Capacité": "256 Go",
                        },
                    },
                    {
                        "sku": "SAMSUNG-GALAXY-256-BLEU",
                        "price": "210000.00",
                        "attributes": {
                            "Couleur": "Bleu",
                            "Capacité": "256 Go",
                        },
                    },
                ],
            },
        ]

        for data in products:

            product, _ = Product.objects.update_or_create(
                slug=data["slug"],
                defaults={
                    "name": data["name"],
                    "description": data["description"],
                    "base_price": data["base_price"],
                    "brand": brands[data["brand"]],
                    "is_active": True,
                },
            )

            # --------------------------------------------------
            # CATEGORIES
            # --------------------------------------------------

            ProductCategory.objects.filter(
                product=product
            ).delete()

            for category_slug in data["categories"]:

                ProductCategory.objects.create(
                    product=product,
                    category=categories[category_slug],
                )

            # --------------------------------------------------
            # IMAGES
            # --------------------------------------------------

            ProductImage.objects.filter(
                product=product
            ).delete()

            for image_url, alt_text, is_primary in data["images"]:

                ProductImage.objects.create(
                    product=product,
                    image_url=image_url,
                    alt_text=alt_text,
                    is_primary=is_primary,
                )

            # --------------------------------------------------
            # VARIANTS
            # --------------------------------------------------

            for variant_data in data["variants"]:

                variant, _ = ProductVariant.objects.update_or_create(
                    sku=variant_data["sku"],
                    defaults={
                        "product": product,
                        "price": variant_data["price"],
                        "is_active": True,
                    },
                )

                # Supprimer les anciennes associations
                VariantAttributeValue.objects.filter(
                    variant=variant
                ).delete()

                # Ajouter les nouveaux attributs
                for (
                    attribute_name,
                    value,
                ) in variant_data["attributes"].items():

                    attribute_value = get_attribute_value(
                        attribute_name,
                        value,
                    )

                    VariantAttributeValue.objects.create(
                        variant=variant,
                        attribute_value=attribute_value,
                    )

            self.stdout.write(
                self.style.SUCCESS(
                    f"  → Produit : {product.name}"
                )
            )

    # ==========================================================
    # STOCKS
    # ==========================================================

    def seed_stocks(self):

        variants = ProductVariant.objects.select_related(
            "product"
        ).order_by("id")

        # Quantités de stock initiales
        stock_quantities = {
            "BOMBAA-TSH-NOIR-M": 50,
            "BOMBAA-TSH-NOIR-L": 40,
            "BOMBAA-TSH-BLANC-M": 35,

            "BOMBAA-JEAN-BLEU-40": 25,
            "BOMBAA-JEAN-BLEU-42": 20,

            "NIKE-AIRMAX-NOIR-42": 15,
            "NIKE-AIRMAX-BLANC-43": 12,

            "ADIDAS-SUPERSTAR-BLANC-41": 18,
            "ADIDAS-SUPERSTAR-NOIR-42": 14,

            "BOMBAA-SAC-NOIR": 30,
            "BOMBAA-SAC-BLEU": 25,

            "SAMSUNG-GALAXY-128-NOIR": 10,
            "SAMSUNG-GALAXY-128-BLANC": 8,

            "SAMSUNG-GALAXY-256-NOIR": 7,
            "SAMSUNG-GALAXY-256-BLEU": 6,
        }

        for variant in variants:

            quantity = stock_quantities.get(
                variant.sku,
                10,
            )

            stock, created = Stock.objects.update_or_create(
                variant=variant,
                defaults={
                    "quantity": quantity,
                    "reserved_quantity": 0,
                    "minimum_quantity": 5,
                },
            )

            # --------------------------------------------------
            # STOCK INITIAL
            # --------------------------------------------------

            if created:

                StockMovement.objects.create(
                    stock=stock,
                    movement_type=StockMovement.MOVEMENT_IN,
                    quantity=quantity,
                    reason="Stock initial",
                )

            self.stdout.write(
                self.style.SUCCESS(
                    f"  → Stock : "
                    f"{variant.sku} = {stock.quantity}"
                )
            )

        self.stdout.write(
            self.style.SUCCESS(
                "✓ Stocks et mouvements initiaux créés."
            )
        )

    def seed_carts(self):
        cart_data = {
            "client1@bombaa.com": [
                ("BOMBAA-TSH-NOIR-M", 2),
                ("NIKE-AIRMAX-NOIR-42", 1),
            ],
            "client2@bombaa.com": [
                ("BOMBAA-JEAN-BLEU-40", 1),
                ("BOMBAA-SAC-NOIR", 1),
            ],
            "client3@bombaa.com": [
                ("SAMSUNG-GALAXY-128-NOIR", 1),
                ("ADIDAS-SUPERSTAR-BLANC-41", 2),
            ],
        }

        for email, items in cart_data.items():
            user = User.objects.get(email=email)

            cart, created = Cart.objects.get_or_create(
                user=user
            )

            for sku, quantity in items:
                variant = ProductVariant.objects.get(sku=sku)

                CartItem.objects.update_or_create(
                    cart=cart,
                    variant=variant,
                    defaults={
                        "quantity": quantity,
                    },
                )

        self.stdout.write(
            self.style.SUCCESS("Paniers de test créés/mis à jour.")
        )

    def seed_wishlists(self):
        wishlist_data = {
            "client1@bombaa.com": [
                "ADIDAS-SUPERSTAR-BLANC-41",
                "SAMSUNG-GALAXY-256-NOIR",
            ],
            "client2@bombaa.com": [
                "BOMBAA-TSH-BLANC-M",
                "NIKE-AIRMAX-BLANC-43",
            ],
            "client3@bombaa.com": [
                "BOMBAA-JEAN-BLEU-42",
                "BOMBAA-SAC-BLEU",
            ],
        }

        for email, skus in wishlist_data.items():
            user = User.objects.get(email=email)

            wishlist, created = Wishlist.objects.get_or_create(
                user=user
            )

            for sku in skus:
                variant = ProductVariant.objects.get(sku=sku)

                WishlistItem.objects.get_or_create(
                    wishlist=wishlist,
                    variant=variant,
                )

        self.stdout.write(
            self.style.SUCCESS("Wishlists de test créées/mises à jour.")
        )

    def seed_orders(self):
        orders_data = [
            {
                "reference": "CMD-SEED-000001",
                "email": "client1@bombaa.com",
                "address_label": "Maison",
                "status": Order.Status.PENDING,
                "items": [
                    ("BOMBAA-TSH-NOIR-M", 2),
                ],
                "shipping_cost": Decimal("1500.00"),
                "discount_amount": Decimal("0.00"),
            },
            {
                "reference": "CMD-SEED-000002",
                "email": "client2@bombaa.com",
                "address_label": "Maison",
                "status": Order.Status.CONFIRMED,
                "items": [
                    ("BOMBAA-JEAN-BLEU-40", 1),
                    ("BOMBAA-SAC-NOIR", 1),
                ],
                "shipping_cost": Decimal("2000.00"),
                "discount_amount": Decimal("1000.00"),
            },
            {
                "reference": "CMD-SEED-000003",
                "email": "client3@bombaa.com",
                "address_label": "Maison",
                "status": Order.Status.PROCESSING,
                "items": [
                    ("SAMSUNG-GALAXY-128-NOIR", 1),
                ],
                "shipping_cost": Decimal("2500.00"),
                "discount_amount": Decimal("0.00"),
            },
        ]

        for data in orders_data:
            user = User.objects.get(email=data["email"])

            address = Address.objects.get(
                user=user,
                label=data["address_label"],
            )

            # Vérifier si la commande existe déjà
            existing_order = Order.objects.filter(
                reference=data["reference"]
            ).first()

            if existing_order:
                self.stdout.write(
                    f"Commande existante conservée : {existing_order.reference}"
                )
                continue

            # ---------------------------------------------------------
            # 1. Calcul du subtotal AVANT création de la commande
            # ---------------------------------------------------------
            prepared_items = []
            subtotal = Decimal("0.00")

            for sku, quantity in data["items"]:
                variant = ProductVariant.objects.select_related(
                    "product"
                ).get(sku=sku)

                unit_price = variant.price
                item_subtotal = unit_price * quantity

                subtotal += item_subtotal

                prepared_items.append({
                    "variant": variant,
                    "quantity": quantity,
                    "unit_price": unit_price,
                    "subtotal": item_subtotal,
                })

            # ---------------------------------------------------------
            # 2. Calcul du total
            # ---------------------------------------------------------
            shipping_cost = data["shipping_cost"]
            discount_amount = data["discount_amount"]

            total_amount = (
                subtotal
                + shipping_cost
                - discount_amount
            )

            # Sécurité
            if total_amount < Decimal("0.00"):
                raise ValueError(
                    f"Le total de la commande {data['reference']} "
                    f"ne peut pas être négatif."
                )

            # ---------------------------------------------------------
            # 3. Création de la commande
            # ---------------------------------------------------------
            order = Order.objects.create(
                user=user,
                reference=data["reference"],
                status=data["status"],
                subtotal=subtotal,
                shipping_cost=shipping_cost,
                discount_amount=discount_amount,
                total_amount=total_amount,
                currency="XOF",
                notes="Commande de test générée par seed_bombaa.",
            )

            # ---------------------------------------------------------
            # 4. Création des lignes de commande
            # ---------------------------------------------------------
            for item in prepared_items:
                variant = item["variant"]

                OrderItem.objects.create(
                    order=order,
                    variant=variant,
                    product_name=variant.product.name,
                    variant_description=f"SKU: {variant.sku}",
                    sku=variant.sku,
                    quantity=item["quantity"],
                    unit_price=item["unit_price"],
                    subtotal=item["subtotal"],
                )

            # ---------------------------------------------------------
            # 5. Création de l'adresse snapshot
            # ---------------------------------------------------------
            OrderAddress.objects.create(
                order=order,
                recipient_name=(
                    f"{address.first_name} {address.last_name}"
                ),
                phone=address.phone,
                address_line1=address.address_line_1,
                address_line2=address.address_line_2,
                city=address.city,
                state=address.state,
                postal_code=address.postal_code,
                country_name=address.country,
                country_code="TG",
            )

            self.stdout.write(
                self.style.SUCCESS(
                    f"Commande créée : {order.reference} "
                    f"| Total : {order.total_amount} XOF"
                )
            )

        self.stdout.write(
            self.style.SUCCESS(
                "Commandes de test créées/mises à jour."
            )
        )
        
    def seed_payments(self):
        payments_data = [
            {
                "order_reference": "CMD-SEED-000001",
                "method_code": "MOBILE_MONEY",
                "status": Payment.Status.PENDING,
            },
            {
                "order_reference": "CMD-SEED-000002",
                "method_code": "CARD",
                "status": Payment.Status.SUCCESS,
            },
            {
                "order_reference": "CMD-SEED-000003",
                "method_code": "MOBILE_MONEY",
                "status": Payment.Status.PROCESSING,
            },
        ]

        for data in payments_data:
            order = Order.objects.get(
                reference=data["order_reference"]
            )

            payment_method = PaymentMethod.objects.get(
                code=data["method_code"]
            )

            payment, created = Payment.objects.get_or_create(
                reference=f"PAY-SEED-{order.id:06d}",
                defaults={
                    "order": order,
                    "payment_method": payment_method,
                    "amount": order.total_amount,
                    "currency": order.currency,
                    "status": data["status"],
                },
            )

            if not created:
                payment.status = data["status"]

                if data["status"] == Payment.Status.SUCCESS:
                    payment.paid_at = timezone.now()

                payment.save(
                    update_fields=[
                        "status",
                        "paid_at",
                        "updated_at",
                    ]
                )

            transaction, transaction_created = Transaction.objects.get_or_create(
                payment=payment,
                defaults={
                    "reference": f"TXN-SEED-{payment.id:06d}",
                    "external_reference": (
                        f"SEED-EXT-{payment.id:06d}"
                        if data["status"] == Payment.Status.SUCCESS
                        else None
                    ),
                    "amount": payment.amount,
                    "currency": payment.currency,
                    "status": (
                        Transaction.Status.SUCCESS
                        if data["status"] == Payment.Status.SUCCESS
                        else Transaction.Status.PENDING
                    ),
                    "response_message": "Transaction générée par seed_bombaa.",
                },
            )

        self.stdout.write(
            self.style.SUCCESS("Paiements et transactions de test créés/mis à jour.")
        )