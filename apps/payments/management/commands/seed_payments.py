from django.core.management.base import BaseCommand

from apps.payments.models import PaymentMethod


class Command(BaseCommand):
    help = "Crée les moyens de paiement de référence de BOMBAA."

    PAYMENT_METHODS = [
        {
            "name": "Mobile Money",
            "code": "MOBILE_MONEY",
            "description": (
                "Paiement par services Mobile Money "
                "disponibles selon le pays."
            ),
        },
        {
            "name": "Carte bancaire",
            "code": "CARD",
            "description": (
                "Paiement par carte bancaire "
                "(Visa, Mastercard, etc.)."
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
                "Paiement effectué lors de la livraison "
                "lorsque cette option est disponible."
            ),
        },
    ]

    def handle(self, *args, **options):
        created_count = 0
        updated_count = 0

        for data in self.PAYMENT_METHODS:
            payment_method, created = (
                PaymentMethod.objects.update_or_create(
                    code=data["code"],
                    defaults={
                        "name": data["name"],
                        "description": data["description"],
                        "is_active": True,
                    },
                )
            )

            if created:
                created_count += 1

                self.stdout.write(
                    self.style.SUCCESS(
                        f"Créé : {payment_method.name}"
                    )
                )
            else:
                updated_count += 1

                self.stdout.write(
                    self.style.WARNING(
                        f"Mis à jour : {payment_method.name}"
                    )
                )

        self.stdout.write("")
        self.stdout.write(
            self.style.SUCCESS(
                "Seed des moyens de paiement terminé."
            )
        )
        self.stdout.write(
            f"Créés : {created_count} | "
            f"Mis à jour : {updated_count}"
        )