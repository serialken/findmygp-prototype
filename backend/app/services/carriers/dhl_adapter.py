"""DHL adapter — real implementation skeleton.

⚠️ Best-effort skeleton, NOT verified against a live account. DHL's public
"MyDHL API" tracking endpoint has historically been:

    GET https://api-eu.dhl.com/track/shipments?trackingNumber=<n>
    Header: DHL-API-Key: <your key>

Before going live: create a developer account at developer.dhl.com, confirm
the current endpoint/auth shape against their docs (it changes), and update
this file accordingly. Until DHL_API_KEY is set in .env, the registry uses
MockCarrierAdapter instead — the app works today either way.
"""

from datetime import datetime
from typing import List

import httpx

from app.config import get_settings
from app.services.carriers.base import CarrierAdapter, CarrierNotConfigured, TrackingEventData

settings = get_settings()

DHL_TRACK_URL = "https://api-eu.dhl.com/track/shipments"


class DHLAdapter(CarrierAdapter):
    name = "dhl"

    def _require_configured(self):
        if not settings.dhl_api_key:
            raise CarrierNotConfigured("DHL_API_KEY manquante dans .env")

    async def create_shipment(self, booking) -> str:
        self._require_configured()
        raise NotImplementedError(
            "Création d'expédition DHL réelle non implémentée — nécessite un contrat "
            "DHL Express/eCommerce et la validation du contrat d'API avec DHL avant intégration."
        )

    async def get_tracking_events(
        self, tracking_number: str, booking_created_at: datetime
    ) -> List[TrackingEventData]:
        self._require_configured()
        headers = {"DHL-API-Key": settings.dhl_api_key}
        params = {"trackingNumber": tracking_number}
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(DHL_TRACK_URL, headers=headers, params=params)
            resp.raise_for_status()
            data = resp.json()

        events: List[TrackingEventData] = []
        shipments = data.get("shipments") or []
        if shipments:
            for event in shipments[0].get("events", []):
                events.append(
                    TrackingEventData(
                        status=_map_dhl_status(event.get("statusCode", "")),
                        note=event.get("description"),
                        timestamp=_parse_dhl_timestamp(event.get("timestamp")),
                        source="dhl",
                    )
                )
        return events


def _map_dhl_status(dhl_status_code: str) -> str:
    mapping = {
        "pre-transit": "confirmed",
        "transit": "in_transit",
        "delivered": "delivered",
        "failure": "pending",
    }
    return mapping.get(dhl_status_code, "in_transit")


def _parse_dhl_timestamp(raw: str) -> datetime:
    try:
        return datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return datetime.utcnow()
