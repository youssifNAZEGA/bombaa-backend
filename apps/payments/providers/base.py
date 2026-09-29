from abc import ABC, abstractmethod
from typing import Any, Dict, Optional


class PaymentProvider(ABC):
    """
    Interface commune de tous les prestataires
    de paiement utilisés par BOMBAA.
    """

    @abstractmethod
    def create_payment(
        self,
        *,
        payment,
        customer: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Initialise un paiement auprès du prestataire.

        Retour attendu, par exemple :

        {
            "success": True,
            "payment_url": "...",
            "external_reference": "...",
            "message": "..."
        }
        """
        raise NotImplementedError

    @abstractmethod
    def check_payment(
        self,
        *,
        payment,
    ) -> Dict[str, Any]:
        """
        Vérifie l'état d'un paiement auprès
        du prestataire.
        """
        raise NotImplementedError

    @abstractmethod
    def handle_webhook(
        self,
        *,
        payload: Dict[str, Any],
        headers: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Traite une notification envoyée par
        le prestataire.
        """
        raise NotImplementedError