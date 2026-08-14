"""Chronopost adapter — real implementation skeleton.

⚠️ Best-effort skeleton, NOT verified against a live account. Chronopost has
historically exposed tracking over a SOAP API (trackingServiceWSStub) tied
to an account number, with newer REST tracking offerings appearing under
La Poste Group's developer portal. Endpoint shapes vary by contract type.

Before going live: confirm the current endpoint/auth shape with your
Chronopost account manager or developer docs. Until CHRONOPOST_API_KEY is
set in .env, the registry uses MockCarrierAdapter.
"""

from datetime import datetime
from typing import List

import httpx

from app.config import get_settings
from app.services.carriers.base import CarrierAdapter, CarrierNotConfigured, TrackingEventData

settings = get_settings()

CHRONOPOST_TRACK_URL = "https://www.chronopost.fr/tracking-cxf/TrackingServiceWS/trackSkybillV2"


class ChronopostAdapter(CarrierAdapter):
    name = "chronopost"

    def _require_configured(self):
        if not settings.chronopost_api_key or not settings.chronopost_account_number:
            raise CarrierNotConfigured(
                "CHRONOPOST_API_KEY / CHRONOPOST_ACCOUNT_NUMBER manquantes dans .env"
            )

    async def create_shipment(self, booking) -> str:
        self._require_configured()
        raise NotImplementedError(
            "Création d'étiquette Chronopost réelle non implémentée — nécessite un contrat "
            "marchand Chronopost avant intégration."
        )

    async def get_tracking_events(
        self, tracking_number: str, booking_created_at: datetime
    ) -> List[TrackingEventData]:
        self._require_configured()
        payload = {
            "accountNumber": settings.chronopost_account_number,
            "password": settings.chronopost_api_key,
            "skybillNumber": tracking_number,
            "language": "fr_FR",
        }
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(CHRONOPOST_TRACK_URL, json=payload)
            resp.raise_for_status()
            data = resp.json()

        events: List[TrackingEventData] = []
        for event in data.get("listEventInfoInquiry", []):
            events.append(
                TrackingEventData(
                    status=_map_chronopost_status(event.get("code", "")),
                    note=event.get("label"),
                    timestamp=_parse_chronopost_timestamp(event.get("date")),
                    source="chronopost",
                )
            )
        return events


def _map_chronopost_status(code: str) -> str:
    mapping = {
        "DC": "confirmed",
        "PC": "picked_up",
        "ET": "in_transit",
        "DI": "delivered",
    }
    return mapping.get(code, "in_transit")


def _parse_chronopost_timestamp(raw: str) -> datetime:
    try:
        return datetime.fromisoformat(raw)
    except (TypeError, ValueError):
        return datetime.utcnow()
