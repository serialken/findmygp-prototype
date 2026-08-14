from fastapi import APIRouter

from app.schemas import DistanceOut, DistanceQuery
from app.services import geocoding_service

router = APIRouter(prefix="/geocoding", tags=["geocoding"])


@router.post("/distance", response_model=DistanceOut)
async def distance(payload: DistanceQuery):
    result = await geocoding_service.estimate_distance_km(
        payload.pickup_address or payload.pickup_city,
        payload.dropoff_address or payload.dropoff_city,
        payload.vehicle,
    )
    return DistanceOut(
        distance_km=result["distance_km"],
        source=result["source"],
        pickup_coordinates=result.get("pickup_coordinates"),
        dropoff_coordinates=result.get("dropoff_coordinates"),
    )
