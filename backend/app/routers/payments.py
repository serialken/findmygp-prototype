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

    try:
        intent = create_payment_intent(booking.price, booking.ref)
    except StripeNotConfigured as exc:
        raise HTTPException(status_code=503, detail=str(exc))

    existing_payment = await db.execute(select(Payment).where(Payment.booking_id == booking.id))
    payment = existing_payment.scalar_one_or_none()
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
                payment.status = PaymentStatus.paid if succeeded else PaymentStatus.failed
                booking_result = await db.execute(select(Booking).where(Booking.id == payment.booking_id))
                booking = booking_result.scalar_one_or_none()
                if booking:
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

    return {"received": True}
