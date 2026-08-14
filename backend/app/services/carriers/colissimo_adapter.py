"""Colissimo (La Poste) adapter — real implementation skeleton.

⚠️ Best-effort skeleton, NOT verified against a live account. La Poste's
"Suivi" tracking API has historically required a contract number + API key
issued via laposte.fr's developer portal, roughly:

    GET https://api.laposte.fr/suivi/v2/idships/<tracking_number>
    Header: X-Okapi-Key: <your key>

Before going live: confirm current auth/endpoint shape with La Poste's
developer docs and your Colissimo merchant contract. Until
COLISSIMO_API_KEY is set in .env, the registry uses MockCarrierAdapter.
"""

from datetime import datetime
from typing import List

import httpx

from app.config import get_settings
from app.services.carriers.base import CarrierAdapter, CarrierNotConfigured, TrackingEventData

settings = get_settings()

COLISSIMO_TRACK_URL = "https://api.laposte.fr/suivi/v2/idships/{tracking_number}"


class ColissimoAdapter(CarrierAdapter):
    name = "colissimo"

    def _require_configured(self):
        if not settings.colissimo_api_key:
            raise CarrierNotConfigured("COLISSIMO_API_KEY manquante dans .env")

    async def create_shipment(self, booking) -> str:
        self._require_configured()
        raise NotImplementedError(
            "Création d'étiquette Colissimo réelle non implémentée — nécessite un contrat "
            "marchand Colissimo (numéro de compte + habilitation Web Services) avant intégration."
        )

    async def get_tracking_events(
        self, tracking_number: str, booking_created_at: datetime
    ) -> List[TrackingEventData]:
        self._require_configured()
        url = COLISSIMO_TRACK_URL.format(tracking_number=tracking_number)
        headers = {"X-Okapi-Key": settings.colissimo_api_key, "Accept": "application/json"}
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(url, headers=headers)
            resp.raise_for_status()
            data = resp.json()

        events: List[TrackingEventData] = []
        for event in (data.get("shipment") or {}).get("event", []):
            events.append(
                TrackingEventData(
                    status=_map_colissimo_status(event.get("code", "")),
                    note=event.get("label"),
                    timestamp=_parse_colissimo_timestamp(event.get("date")),
                    source="colissimo",
                )
            )
        return events


def _map_colissimo_status(code: str) -> str:
    mapping = {
        "PC1": "confirmed",
        "ET1": "picked_up",
        "DO1": "in_transit",
        "DI1": "delivered",
    }
    return mapping.get(code, "in_transit")


def _parse_colissimo_timestamp(raw: str) -> datetime:
    try:
        return datetime.fromisoformat(raw)
    except (TypeError, ValueError):
        return datetime.utcnow()
