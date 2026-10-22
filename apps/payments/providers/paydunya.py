import requests

from django.conf import settings

from .base import PaymentProvider


class PayDunyaProvider(PaymentProvider):
    """
    Provider PayDunya pour BOMBAA.

    Utilise Checkout Invoice / Payment & Redirection.
    """

    def __init__(self):
        self.master_key = settings.PAYDUNYA_MASTER_KEY
        self.private_key = settings.PAYDUNYA_PRIVATE_KEY
        self.public_key = settings.PAYDUNYA_PUBLIC_KEY
        self.token = settings.PAYDUNYA_TOKEN

        self.create_url = settings.PAYDUNYA_CHECKOUT_CREATE_URL
        self.confirm_url = settings.PAYDUNYA_CHECKOUT_CONFIRM_URL

        self.store_name = settings.PAYDUNYA_STORE_NAME
        self.return_url = settings.PAYDUNYA_RETURN_URL
        self.cancel_url = settings.PAYDUNYA_CANCEL_URL
        self.callback_url = settings.PAYDUNYA_CALLBACK_URL

    def _headers(self):
        return {
            "Content-Type": "application/json",
            "PAYDUNYA-MASTER-KEY": self.master_key,
            "PAYDUNYA-PRIVATE-KEY": self.private_key,
            "PAYDUNYA-TOKEN": self.token,
        }

    def _validate_configuration(self):
        required = {
            "PAYDUNYA_MASTER_KEY": self.master_key,
            "PAYDUNYA_PRIVATE_KEY": self.private_key,
            "PAYDUNYA_TOKEN": self.token,
        }

        missing = [
            name
            for name, value in required.items()
            if not value
        ]

        if missing:
            raise ValueError(
                "Configuration PayDunya incomplète : "
                + ", ".join(missing)
            )

    def create_payment(self, *, payment, customer):
        self._validate_configuration()

        order = payment.order

        items = {}

        for index, item in enumerate(
            order.items.select_related("variant", "variant__product")
        ):
            items[f"item_{index}"] = {
                "name": item.product_name,
                "quantity": item.quantity,
                "unit_price": str(item.unit_price),
                "total_price": str(item.subtotal),
                "description": item.variant_description or "",
            }

        customer_name = customer.get("name", "")
        customer_email = customer.get("email", "")
        customer_phone = customer.get("phone", "")

        payload = {
            "invoice": {
                "items": items,
                "customer": {
                    "name": customer_name,
                    "email": customer_email,
                    "phone": customer_phone,
                },
                "total_amount": float(payment.amount),
                "description": (
                    f"Commande {order.reference} - BOMBAA"
                ),
            },
            "store": {
                "name": self.store_name,
            },
            "custom_data": {
                "payment_reference": payment.reference,
                "order_reference": order.reference,
            },
            "actions": {
                "return_url": self.return_url,
                "cancel_url": self.cancel_url,
                "callback_url": self.callback_url,
            },
        }

        response = requests.post(
            self.create_url,
            json=payload,
            headers=self._headers(),
            timeout=30,
        )

        response.raise_for_status()

        data = response.json()

        if data.get("response_code") != "00":
            raise ValueError(
                data.get(
                    "response_text",
                    "Erreur PayDunya inconnue.",
                )
            )

        token = data.get("token")
        checkout_url = data.get("response_text")

        if not token or not checkout_url:
            raise ValueError(
                "Réponse PayDunya invalide : "
                "token ou URL de paiement manquant."
            )

        return {
            "success": True,
            "token": token,
            "checkout_url": checkout_url,
            "response_code": data.get("response_code"),
            "response_text": data.get("response_text"),
        }

    def check_payment(self, *, payment):
        self._validate_configuration()

        transaction = (
            payment.transactions
            .order_by("-created_at")
            .first()
        )

        if not transaction or not transaction.external_reference:
            raise ValueError(
                "Token PayDunya introuvable pour ce paiement."
            )

        token = transaction.external_reference

        url = f"{self.confirm_url}/{token}"

        response = requests.get(
            url,
            headers=self._headers(),
            timeout=30,
        )

        response.raise_for_status()

        return response.json()

    def handle_webhook(self, *, payload, headers=None):
        return payload