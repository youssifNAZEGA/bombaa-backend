from django.core.management.base import BaseCommand

from apps.accounts.models import Role, Permission


class Command(BaseCommand):

    help = "Initialise les rôles et permissions de BOMBAA"

    def handle(self, *args, **options):

        permissions = [
            # Utilisateurs
            ("users.view", "Consulter les utilisateurs"),
            ("users.create", "Créer un utilisateur"),
            ("users.update", "Modifier un utilisateur"),
            ("users.delete", "Supprimer un utilisateur"),

            # Rôles
            ("roles.view", "Consulter les rôles"),
            ("roles.create", "Créer un rôle"),
            ("roles.update", "Modifier un rôle"),
            ("roles.delete", "Supprimer un rôle"),

            # Permissions
            ("permissions.view", "Consulter les permissions"),
            ("permissions.create", "Créer une permission"),
            ("permissions.update", "Modifier une permission"),
            ("permissions.delete", "Supprimer une permission"),

            # Catégories
            ("categories.view", "Consulter les catégories"),
            ("categories.create", "Créer une catégorie"),
            ("categories.update", "Modifier une catégorie"),
            ("categories.delete", "Supprimer une catégorie"),

            # Produits
            ("products.view", "Consulter les produits"),
            ("products.create", "Créer un produit"),
            ("products.update", "Modifier un produit"),
            ("products.delete", "Supprimer un produit"),

            # Commandes
            ("orders.view", "Consulter les commandes"),
            ("orders.create", "Créer une commande"),
            ("orders.update", "Modifier une commande"),
            ("orders.delete", "Supprimer une commande"),

            # Paiements
            ("payments.view", "Consulter les paiements"),
            ("payments.create", "Créer un paiement"),
            ("payments.update", "Modifier un paiement"),

            # Avis
            ("reviews.view", "Consulter les avis"),
            ("reviews.create", "Créer un avis"),
            ("reviews.update", "Modifier un avis"),
            ("reviews.delete", "Supprimer un avis"),

            # Retours
            ("returns.view", "Consulter les retours"),
            ("returns.create", "Créer un retour"),
            ("returns.update", "Modifier un retour"),

            # Remboursements
            ("refunds.view", "Consulter les remboursements"),
            ("refunds.create", "Créer un remboursement"),
            ("refunds.update", "Modifier un remboursement"),

            # Notifications
            ("notifications.view", "Consulter les notifications"),
            ("notifications.create", "Créer une notification"),

            # Support
            ("support.view", "Consulter le support"),
            ("support.create", "Créer un ticket support"),
            ("support.update", "Modifier un ticket support"),
        ]

        permission_objects = {}

        for name, description in permissions:
            permission, created = Permission.objects.get_or_create(
                name=name,
                defaults={
                    "description": description
                }
            )

            permission_objects[name] = permission

            if created:
                self.stdout.write(
                    self.style.SUCCESS(
                        f"Permission créée : {name}"
                    )
                )

        # ==========================
        # RÔLE ADMIN
        # ==========================

        admin_role, created = Role.objects.get_or_create(
            name="ADMIN",
            defaults={
                "description": "Administrateur de la plateforme BOMBAA"
            }
        )

        if created:
            self.stdout.write(
                self.style.SUCCESS("Rôle ADMIN créé")
            )

        admin_role.permissions.set(
            permission_objects.values()
        )

        # ==========================
        # RÔLE CLIENT
        # ==========================

        client_role, created = Role.objects.get_or_create(
            name="CLIENT",
            defaults={
                "description": "Client de la plateforme BOMBAA"
            }
        )

        if created:
            self.stdout.write(
                self.style.SUCCESS("Rôle CLIENT créé")
            )

        client_permission_names = [
            "products.view",
            "categories.view",

            "orders.view",
            "orders.create",

            "payments.view",
            "payments.create",

            "reviews.view",
            "reviews.create",
            "reviews.update",
            "reviews.delete",

            "returns.view",
            "returns.create",

            "refunds.view",

            "notifications.view",

            "support.view",
            "support.create",
            "support.update",
        ]

        client_role.permissions.set(
            permission_objects[name]
            for name in client_permission_names
        )

        self.stdout.write("")
        self.stdout.write(
            self.style.SUCCESS(
                " Rôles et permissions BOMBAA initialisés avec succès."
            )
        )