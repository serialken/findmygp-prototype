"""Default adapter used whenever a real carrier API key isn't configured.

Simulates a realistic status progression on an ACCELERATED clock (minutes,
not days) so the flow is demoable end-to-end without waiting for a real
shipment to move. Swap in a real adapter (see chronopost_adapter.py etc.)
by setting the corresponding API key in .env — the registry picks it up
automatically, no code changes required.
"""

import hashlib
import random
from datetime import datetime, timedelta
from typing import List

from app.services.carriers.base import CarrierAdapter, TrackingEventData

# Elapsed time (in seconds, real wall-clock since booking creation) at which
# each status kicks in. Tuned for demo purposes.
_THRESHOLDS = [
    (0, "confirmed", "Prise en charge confirmée par le transporteur."),
    (20, "picked_up", "Colis récupéré par le transporteur."),
    (90, "in_transit", "Colis en cours d'acheminement."),
    (240, "delivered", "Colis livré."),
]


class MockCarrierAdapter(CarrierAdapter):
    name = "mock"

    async def create_shipment(self, booking) -> str:
        seed = f"{booking.id}-{booking.carrier_id}".encode()
        digest = hashlib.sha1(seed).hexdigest()[:10].upper()
        prefix = {"chronopost": "CHR", "colissimo": "COL", "dhl": "DHL"}.get(
            getattr(booking, "external_network", None), "SIM"
        )
        return f"{prefix}{digest}"

    async def get_tracking_events(
        self, tracking_number: str, booking_created_at: datetime
    ) -> List[TrackingEventData]:
        elapsed = (datetime.utcnow() - booking_created_at).total_seconds()
        events: List[TrackingEventData] = []
        rng = random.Random(tracking_number)
        for offset, status, note in _THRESHOLDS:
            if elapsed >= offset:
                jitter = timedelta(seconds=rng.randint(0, 5))
                events.append(
                    TrackingEventData(
                        status=status,
                        note=note,
                        timestamp=booking_created_at + timedelta(seconds=offset) + jitter,
                        source="mock",
                    )
                )
        return events
