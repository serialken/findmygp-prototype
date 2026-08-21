import stripe

from app.config import get_settings

settings = get_settings()
stripe.api_key = settings.stripe_secret_key


class StripeNotConfigured(Exception):
    pass


def _require_configured():
    if not settings.stripe_secret_key:
        raise StripeNotConfigured(
            "STRIPE_SECRET_KEY n'est pas configurée — ajoute tes clés Stripe test dans backend/.env"
        )


def create_payment_intent(amount_eur: float, booking_ref: str, currency: str = "eur") -> stripe.PaymentIntent:
    _require_configured()
    amount_cents = round(amount_eur * 100)
    # payment_method_types=["card"], not automatic_payment_methods: the frontend
    # uses the classic Card Element + confirmCardPayment(), not the newer Payment
    # Element. automatic_payment_methods opts into dashboard-configured methods
    # that can include redirect-based ones, which require a return_url and don't
    # pair cleanly with confirmCardPayment.
    return stripe.PaymentIntent.create(
        amount=amount_cents,
        currency=currency,
        metadata={"booking_ref": booking_ref},
        payment_method_types=["card"],
    )


def construct_webhook_event(payload: bytes, sig_header: str) -> stripe.Event:
    _require_configured()
    if not settings.stripe_webhook_secret:
        raise StripeNotConfigured(
            "STRIPE_WEBHOOK_SECRET n'est pas configurée — nécessaire pour vérifier les webhooks Stripe"
        )
    return stripe.Webhook.construct_event(payload, sig_header, settings.stripe_webhook_secret)
