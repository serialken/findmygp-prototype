from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.deps import get_current_user
from app.models import CarrierProfile, User
from app.schemas import CarrierOut

router = APIRouter(prefix="/carriers", tags=["carriers"])


@router.get("", response_model=List[CarrierOut])
async def search_carriers(
    pickup_city: Optional[str] = Query(default=None),
    dropoff_city: Optional[str] = Query(default=None),
    package_type: Optional[str] = Query(default=None),
    vehicle: Optional[str] = Query(default=None),
    max_price: Optional[float] = Query(default=None),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(CarrierProfile))
    carriers = result.scalars().all()

    def matches_city(carrier: CarrierProfile, city: str) -> bool:
        q = city.lower()
        return q in carrier.city.lower() or any(q in z.lower() for z in carrier.zones_served)

    filtered = []
    for c in carriers:
        if pickup_city and not matches_city(c, pickup_city):
            continue
        if dropoff_city and not matches_city(c, dropoff_city):
            continue
        if package_type and package_type not in c.package_types:
            continue
        if vehicle and c.vehicle.value != vehicle:
            continue
        if max_price is not None and c.base_price > max_price:
            continue
        filtered.append(c)

    filtered.sort(key=lambda c: c.rating, reverse=True)
    return filtered


@router.get("/{carrier_id}", response_model=CarrierOut)
async def get_carrier(carrier_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(CarrierProfile).where(CarrierProfile.id == carrier_id))
    carrier = result.scalar_one_or_none()
    if not carrier:
        raise HTTPException(status_code=404, detail="Transporteur introuvable")
    return carrier


@router.post("/{carrier_id}/link-account", response_model=CarrierOut)
async def link_carrier_account(
    carrier_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Links the authenticated carrier-role account to one of the (currently
    unclaimed, pre-seeded) carrier profiles, so that account can log tracking
    updates and messages as that carrier. One profile <-> one account, strictly."""
    if current_user.role.value != "carrier":
        raise HTTPException(
            status_code=403, detail="Seul un compte transporteur peut être lié à un profil transporteur"
        )

    result = await db.execute(select(CarrierProfile).where(CarrierProfile.id == carrier_id))
    carrier = result.scalar_one_or_none()
    if not carrier:
        raise HTTPException(status_code=404, detail="Transporteur introuvable")

    if carrier.user_id is not None and carrier.user_id != current_user.id:
        raise HTTPException(status_code=409, detail="Ce profil transporteur est déjà lié à un autre compte")

    if current_user.carrier_profile is not None and current_user.carrier_profile.id != carrier.id:
        raise HTTPException(status_code=409, detail="Ce compte est déjà lié à un autre profil transporteur")

    carrier.user_id = current_user.id
    await db.commit()
    await db.refresh(carrier)
    return carrier


@router.delete("/{carrier_id}/link-account", response_model=CarrierOut)
async def unlink_carrier_account(
    carrier_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Unlinks a carrier profile from its account — only the linked account
    itself or an admin can do this. Idempotent: unlinking an already-unclaimed
    profile is a no-op, not an error."""
    result = await db.execute(select(CarrierProfile).where(CarrierProfile.id == carrier_id))
    carrier = result.scalar_one_or_none()
    if not carrier:
        raise HTTPException(status_code=404, detail="Transporteur introuvable")

    if carrier.user_id is None:
        return carrier

    if carrier.user_id != current_user.id and current_user.role.value != "admin":
        raise HTTPException(
            status_code=403, detail="Seul le compte lié (ou un administrateur) peut délier ce profil"
        )

    carrier.user_id = None
    await db.commit()
    await db.refresh(carrier)
    return carrier
