from typing import List

from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database import AsyncSessionLocal, get_db
from app.deps import get_current_user
from app.models import Booking, BookingStatus, CarrierProfile, TrackingEvent, User
from app.schemas import TrackingEventOut, TrackingUpdateIn
from app.security import decode_token
from app.services.carriers.registry import get_adapter
from app.websockets.manager import tracking_manager

router = APIRouter(tags=["tracking"])


async def _get_authorized_booking(db: AsyncSession, booking_id: str, current_user: User) -> Booking:
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


@router.get("/tracking/{booking_id}", response_model=List[TrackingEventOut])
async def get_tracking(
    booking_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    booking = await _get_authorized_booking(db, booking_id, current_user)
    result = await db.execute(
        select(TrackingEvent).where(TrackingEvent.booking_id == booking.id).order_by(TrackingEvent.created_at)
    )
    return result.scalars().all()


@router.patch("/tracking/{booking_id}", response_model=List[TrackingEventOut])
async def update_tracking(
    booking_id: str,
    payload: TrackingUpdateIn,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Manual status update — used by the carrier (or an internal ops tool)
    to advance a booking's status. Persists the event and broadcasts it to
    everyone subscribed on the tracking WebSocket for this booking."""
    booking = await _get_authorized_booking(db, booking_id, current_user)
    is_owner_carrier = (
        current_user.carrier_profile is not None and booking.carrier_id == current_user.carrier_profile.id
    )
    if not (is_owner_carrier or current_user.role.value == "admin"):
        raise HTTPException(status_code=403, detail="Seul le transporteur peut mettre à jour le statut")

    try:
        new_status = BookingStatus(payload.status)
    except ValueError:
        raise HTTPException(status_code=422, detail="Statut invalide")

    booking.status = new_status
    event = TrackingEvent(booking_id=booking.id, status=new_status, note=payload.note, source="internal")
    db.add(event)
    await db.commit()
    await db.refresh(event)

    await tracking_manager.broadcast(
        booking.id,
        {
            "type": "tracking_update",
            "status": new_status.value,
            "note": payload.note,
            "created_at": event.created_at.isoformat(),
        },
    )

    result = await db.execute(
        select(TrackingEvent).where(TrackingEvent.booking_id == booking.id).order_by(TrackingEvent.created_at)
    )
    return result.scalars().all()


@router.post("/tracking/{booking_id}/sync", response_model=List[TrackingEventOut])
async def sync_external_tracking(
    booking_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Pulls the latest status from the external carrier network (real API if
    configured, otherwise the accelerated mock simulation) and persists any
    new events, broadcasting each one over the tracking WebSocket."""
    booking = await _get_authorized_booking(db, booking_id, current_user)
    if not booking.external_tracking_number:
        return []

    carrier = await db.get(CarrierProfile, booking.carrier_id)
    adapter = get_adapter(carrier.external_network.value if carrier else "none")
    external_events = await adapter.get_tracking_events(booking.external_tracking_number, booking.created_at)

    existing = await db.execute(
        select(TrackingEvent.status).where(TrackingEvent.booking_id == booking.id)
    )
    known_statuses = {row[0].value if hasattr(row[0], "value") else row[0] for row in existing}

    new_events = []
    for ev in external_events:
        if ev.status in known_statuses:
            continue
        db_event = TrackingEvent(
            booking_id=booking.id, status=BookingStatus(ev.status), note=ev.note, source=ev.source,
            created_at=ev.timestamp,
        )
        db.add(db_event)
        new_events.append(db_event)
        known_statuses.add(ev.status)
        booking.status = BookingStatus(ev.status)

    if new_events:
        await db.commit()
        for db_event in new_events:
            await db.refresh(db_event)
            await tracking_manager.broadcast(
                booking.id,
                {
                    "type": "tracking_update",
                    "status": db_event.status.value,
                    "note": db_event.note,
                    "created_at": db_event.created_at.isoformat(),
                },
            )

    result = await db.execute(
        select(TrackingEvent).where(TrackingEvent.booking_id == booking.id).order_by(TrackingEvent.created_at)
    )
    return result.scalars().all()


@router.websocket("/ws/tracking/{booking_id}")
async def tracking_ws(websocket: WebSocket, booking_id: str, token: str):
    payload = decode_token(token)
    if not payload or payload.get("type") != "access":
        await websocket.close(code=4401)
        return

    async with AsyncSessionLocal() as db:
        result = await db.execute(select(Booking).where(Booking.id == booking_id))
        booking = result.scalar_one_or_none()
        result_user = await db.execute(
            select(User).where(User.id == payload.get("sub")).options(selectinload(User.carrier_profile))
        )
        user = result_user.scalar_one_or_none()
        if not booking or not user:
            await websocket.close(code=4404)
            return
        is_owner_client = booking.client_id == user.id
        is_owner_carrier = user.carrier_profile is not None and booking.carrier_id == user.carrier_profile.id
        if not (is_owner_client or is_owner_carrier or user.role.value == "admin"):
            await websocket.close(code=4403)
            return

    await tracking_manager.connect(booking_id, websocket)
    try:
        while True:
            await websocket.receive_text()  # keep-alive / ignored client pings
    except WebSocketDisconnect:
        tracking_manager.disconnect(booking_id, websocket)
