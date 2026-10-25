from decimal import Decimal, ROUND_HALF_UP

from .models import Currency


MONEY_QUANTUM = Decimal("0.01")


class CurrencyService:

    @staticmethod
    def base_currency():
        return (
            Currency.objects
            .filter(is_active=True, is_base=True)
            .first()
            or Currency.objects.filter(is_active=True).first()
        )

    @staticmethod
    def base_currency_code(fallback="XOF"):
        currency = CurrencyService.base_currency()

        return currency.code if currency else fallback

    @staticmethod
    def get_active_currency(code):
        if not code:
            return None

        return (
            Currency.objects
            .filter(
                is_active=True,
                code__iexact=code.strip(),
            )
            .first()
        )

    @staticmethod
    def convert(amount, source, target):
        amount = Decimal(amount)

        if source is None or target is None:
            return amount.quantize(
                MONEY_QUANTUM,
                rounding=ROUND_HALF_UP,
            )

        amount_in_base = amount * source.exchange_rate

        return (
            amount_in_base / target.exchange_rate
        ).quantize(
            MONEY_QUANTUM,
            rounding=ROUND_HALF_UP,
        )
