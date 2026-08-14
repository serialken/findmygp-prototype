from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import CarrierProfile
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
