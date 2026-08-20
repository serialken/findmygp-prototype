import random
import string
from datetime import datetime
from typing import List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.deps import get_current_user
from app.models import Booking, BookingStatus, CarrierProfile, Conversation, TrackingEvent, User
from app.schemas import BookingCreate, BookingOut, BookingQuote, DistanceQuery
from app.services import geocoding_service, pricing_service
from app.services.carriers.base import CarrierNotConfigured
from app.services.carriers.registry import get_adapter

router = APIRouter(prefix="/bookings", tags=["bookings"])


def _generate_ref() -> str:
    now = datetime.utcnow()
    code = "".join(random.choices(string.ascii_uppercase + string.digits, k=5))
    return f"LC-{now.strftime('%Y%m')}-{code}"


def _generate_confirmation_code() -> str:
    return "".join(random.choices(string.digits, k=4))


async def _get_carrier_or_404(db: AsyncSession, carrier_id: str) -> CarrierProfile:
    result = await db.execute(select(CarrierProfile).where(CarrierProfile.id == carrier_id))
    carrier = result.scalar_one_or_none()
    if not carrier:
        raise HTTPException(status_code=404, detail="Transporteur introuvable")
    return carrier


@router.post("/quote", response_model=BookingQuote)
async def quote_booking(payload: DistanceQuery, db: AsyncSession = Depends(get_db)):
    """Public price preview — read-only, uses the exact same pricing formula
    as booking creation so the number shown before submitting always matches
    what POST /bookings will actually charge. Pass carrier_id for a real
    per-carrier price using that carrier's rates and vehicle (falls back to a
    generic distance-only estimate if no carrier is picked yet)."""
    vehicle = payload.vehicle
    base_price = 0.0
    price_per_km = 1.0

    if payload.carrier_id:
        carrier = await _get_carrier_or_404(db, payload.carrier_id)
        vehicle = carrier.vehicle.value
        base_price = carrier.base_price
        price_per_km = carrier.price_per_km

    distance = await geocoding_service.estimate_distance_km(
        payload.pickup_address or payload.pickup_city,
        payload.dropoff_address or payload.dropoff_city,
        vehicle,
    )
    priced = pricing_service.compute_price(base_price, price_per_km, distance["distance_km"], payload.fragile)
    return BookingQuote(
        distance_km=distance["distance_km"],
        distance_source=distance["source"],
        base_price=priced["base_price"],
        distance_price=priced["distance_price"],
        fragile_surcharge=priced["fragile_surcharge"],
        total_price=priced["total_price"],
    )


@router.post("", response_model=BookingOut, status_code=201)
async def create_booking(
    payload: BookingCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    carrier = await _get_carrier_or_404(db, payload.carrier_id)

    pickup_query = f"{payload.pickup_address}, {payload.pickup_city}"
    dropoff_query = f"{payload.dropoff_address}, {payload.dropoff_city}"
    distance = await geocoding_service.estimate_distance_km(pickup_query, dropoff_query, carrier.vehicle.value)

    # Price is ALWAYS computed server-side from the carrier's real rates —
    # never trust a price sent by the client, since this is what gets charged.
    priced = pricing_service.compute_price(
        carrier.base_price, carrier.price_per_km, distance["distance_km"], payload.fragile
    )

    pickup_coords = distance.get("pickup_coordinates") or [None, None]
    dropoff_coords = distance.get("dropoff_coordinates") or [None, None]

    booking = Booking(
        ref=_generate_ref(),
        client_id=current_user.id,
        carrier_id=carrier.id,
        pickup_address=payload.pickup_address,
        pickup_city=payload.pickup_city,
        pickup_postal_code=payload.pickup_postal_code,
        pickup_lat=pickup_coords[0],
        pickup_lng=pickup_coords[1],
        dropoff_address=payload.dropoff_address,
        dropoff_city=payload.dropoff_city,
        dropoff_postal_code=payload.dropoff_postal_code,
        dropoff_lat=dropoff_coords[0],
        dropoff_lng=dropoff_coords[1],
        package_type=payload.package_type,
        weight_kg=payload.weight_kg,
        dimensions=payload.dimensions,
        description=payload.description,
        fragile=payload.fragile,
        requested_date=payload.requested_date,
        time_window=payload.time_window,
        distance_km=distance["distance_km"],
        distance_source=distance["source"],
        price=priced["total_price"],
        status=BookingStatus.pending,
        confirmation_code=_generate_confirmation_code(),
    )
    db.add(booking)
    await db.flush()

    db.add(TrackingEvent(booking_id=booking.id, status=BookingStatus.pending, note="Demande envoyée au transporteur.", source="internal"))

    # Register with the external carrier network if this carrier is affiliated
    # with one (falls back to the mock/simulation adapter automatically if no
    # real API key is configured, or if real shipment creation isn't wired up yet).
    external_network = carrier.external_network.value
    if external_network != "none":
        # Transient hint (not a mapped column) so the mock adapter can prefix
        # the simulated tracking number with the right network, e.g. "DHL...".
        booking.external_network = external_network
        adapter = get_adapter(external_network)
        try:
            booking.external_tracking_number = await adapter.create_shipment(booking)
        except (CarrierNotConfigured, NotImplementedError):
            from app.services.carriers.mock_adapter import MockCarrierAdapter

            booking.external_tracking_number = await MockCarrierAdapter().create_shipment(booking)

    # Ensure a conversation exists between this client and carrier, linked to the booking
    existing_conv = await db.execute(
        select(Conversation).where(
            Conversation.client_id == current_user.id, Conversation.carrier_id == carrier.id
        )
    )
    conversation = existing_conv.scalar_one_or_none()
    if conversation:
        conversation.booking_id = booking.id
    else:
        db.add(Conversation(booking_id=booking.id, client_id=current_user.id, carrier_id=carrier.id))

    await db.commit()
    await db.refresh(booking)
    return booking


@router.get("/mine", response_model=List[BookingOut])
async def list_my_bookings(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if current_user.role.value == "carrier" and current_user.carrier_profile:
        result = await db.execute(
            select(Booking).where(Booking.carrier_id == current_user.carrier_profile.id).order_by(Booking.created_at.desc())
        )
    else:
        result = await db.execute(
            select(Booking).where(Booking.client_id == current_user.id).order_by(Booking.created_at.desc())
        )
    return result.scalars().all()


@router.get("/{booking_id}", response_model=BookingOut)
async def get_booking(
    booking_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Booking).where(Booking.id == booking_id))
    booking = result.scalar_one_or_none()
    if not booking:
        raise HTTPException(status_code=404, detail="Réservation introuvable")

    is_owner_client = booking.client_id == current_user.id
    is_owner_carrier = (
        current_user.carrier_profile is not None and booking.carrier_id == current_user.carrier_profile.id
    )
    if not (is_owner_client or is_owner_carrier or current_user.role.value == "admin"):
        raise HTTPException(status_code=403, detail="Accès non autorisé à cette réservation")

    return booking
