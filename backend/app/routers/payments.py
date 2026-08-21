import stripe
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.database import AsyncSessionLocal, get_db
from app.deps import get_current_user
from app.models import Booking, BookingStatus, Payment, PaymentStatus, TrackingEvent, User
from app.schemas import PaymentIntentOut
from app.services.payment_service import StripeNotConfigured, construct_webhook_event, create_payment_intent
from app.websockets.manager import tracking_manager

router = APIRouter(prefix="/payments", tags=["payments"])
settings = get_settings()


async def _apply_payment_result(db: AsyncSession, payment: Payment, succeeded: bool):
    """Shared by the webhook and the sync confirm fallback: marks the payment
    and booking paid/failed, and — on the first successful payment — advances
    the booking to 'confirmed' and broadcasts that over the tracking WebSocket."""
    payment.status = PaymentStatus.paid if succeeded else PaymentStatus.failed
    result = await db.execute(select(Booking).where(Booking.id == payment.booking_id))
    booking = result.scalar_one_or_none()
    if not booking:
        await db.commit()
        return None

    booking.payment_status = PaymentStatus.paid if succeeded else PaymentStatus.failed
    if succeeded and booking.status == BookingStatus.pending:
        booking.status = BookingStatus.confirmed
        event_row = TrackingEvent(
            booking_id=booking.id,
            status=BookingStatus.confirmed,
            note="Paiement confirmé — livraison validée par le transporteur.",
            source="internal",
        )
        db.add(event_row)
        await db.commit()
        await db.refresh(event_row)
        await tracking_manager.broadcast(
            booking.id,
            {
                "type": "tracking_update",
                "status": event_row.status.value,
                "note": event_row.note,
                "created_at": event_row.created_at.isoformat(),
            },
        )
    else:
        await db.commit()
    return booking


@router.post("/bookings/{booking_id}/intent", response_model=PaymentIntentOut)
async def create_intent_for_booking(
    booking_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Booking).where(Booking.id == booking_id))
    booking = result.scalar_one_or_none()
    if not booking:
        raise HTTPException(status_code=404, detail="Réservation introuvable")
    if booking.client_id != current_user.id:
        raise HTTPException(status_code=403, detail="Accès non autorisé à cette réservation")
    if booking.payment_status == PaymentStatus.paid:
        raise HTTPException(status_code=409, detail="Cette réservation est déjà payée")

    existing_payment = await db.execute(select(Payment).where(Payment.booking_id == booking.id))
    payment = existing_payment.scalar_one_or_none()

    # Re-clicking "Payer" (e.g. after a page reload before the booking got
    # reconciled) must NOT blindly create a new Stripe PaymentIntent — that
    # would orphan a still-open or already-succeeded one and risk a double
    # charge. Check the existing intent's real status with Stripe first.
    if payment and payment.stripe_payment_intent_id:
        try:
            existing_intent = stripe.PaymentIntent.retrieve(payment.stripe_payment_intent_id)
        except stripe.error.StripeError:
            existing_intent = None
        if existing_intent is not None:
            if existing_intent.status == "succeeded":
                await _apply_payment_result(db, payment, succeeded=True)
                raise HTTPException(status_code=409, detail="Cette réservation est déjà payée")
            if existing_intent.status in ("requires_payment_method", "requires_confirmation", "requires_action"):
                return PaymentIntentOut(
                    client_secret=existing_intent.client_secret,
                    publishable_key=settings.stripe_publishable_key,
                    amount_cents=existing_intent.amount,
                    currency=existing_intent.currency,
                )

    try:
        intent = create_payment_intent(booking.price, booking.ref)
    except StripeNotConfigured as exc:
        raise HTTPException(status_code=503, detail=str(exc))

    if payment:
        payment.stripe_payment_intent_id = intent.id
        payment.amount_cents = intent.amount
        payment.status = PaymentStatus.processing
    else:
        payment = Payment(
            booking_id=booking.id,
            stripe_payment_intent_id=intent.id,
            amount_cents=intent.amount,
            currency=intent.currency,
            status=PaymentStatus.processing,
        )
        db.add(payment)

    booking.payment_status = PaymentStatus.processing
    await db.commit()

    return PaymentIntentOut(
        client_secret=intent.client_secret,
        publishable_key=settings.stripe_publishable_key,
        amount_cents=intent.amount,
        currency=intent.currency,
    )


@router.post("/webhook")
async def stripe_webhook(request: Request):
    payload = await request.body()
    sig_header = request.headers.get("stripe-signature", "")

    try:
        event = construct_webhook_event(payload, sig_header)
    except StripeNotConfigured as exc:
        raise HTTPException(status_code=503, detail=str(exc))
    except (stripe.error.SignatureVerificationError, ValueError):
        raise HTTPException(status_code=400, detail="Signature de webhook invalide")

    if event["type"] in ("payment_intent.succeeded", "payment_intent.payment_failed"):
        intent = event["data"]["object"]
        succeeded = event["type"] == "payment_intent.succeeded"

        async with AsyncSessionLocal() as db:
            result = await db.execute(
                select(Payment).where(Payment.stripe_payment_intent_id == intent["id"])
            )
            payment = result.scalar_one_or_none()
            if payment:
                await _apply_payment_result(db, payment, succeeded)

    return {"received": True}


@router.post("/bookings/{booking_id}/confirm")
async def confirm_payment_status(
    booking_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Synchronous fallback for environments where Stripe's webhook can't
    reach the API (e.g. localhost in dev) — the frontend calls this right
    after stripe.confirmCardPayment() resolves. Never trusts the client's
    claim of success: re-fetches the PaymentIntent from Stripe's API and
    only marks the booking paid if Stripe itself reports it succeeded. The
    webhook remains the source of truth in any environment where it can
    actually be delivered; this just closes the gap where it can't."""
    result = await db.execute(select(Booking).where(Booking.id == booking_id))
    booking = result.scalar_one_or_none()
    if not booking:
        raise HTTPException(status_code=404, detail="Réservation introuvable")
    if booking.client_id != current_user.id:
        raise HTTPException(status_code=403, detail="Accès non autorisé à cette réservation")

    payment_result = await db.execute(select(Payment).where(Payment.booking_id == booking.id))
    payment = payment_result.scalar_one_or_none()
    if not payment:
        raise HTTPException(status_code=404, detail="Aucun paiement initié pour cette réservation")

    if payment.status == PaymentStatus.paid:
        return {"payment_status": "paid"}

    try:
        intent = stripe.PaymentIntent.retrieve(payment.stripe_payment_intent_id)
    except stripe.error.StripeError as exc:
        raise HTTPException(status_code=502, detail=str(exc))

    if intent.id != payment.stripe_payment_intent_id:
        raise HTTPException(status_code=400, detail="Intention de paiement invalide")

    if intent.status == "succeeded":
        await _apply_payment_result(db, payment, succeeded=True)
        return {"payment_status": "paid"}

    if intent.status in ("canceled",):
        await _apply_payment_result(db, payment, succeeded=False)
        return {"payment_status": "failed"}

    return {"payment_status": payment.status.value, "stripe_status": intent.status}
