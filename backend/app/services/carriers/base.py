from abc import ABC, abstractmethod
from datetime import datetime
from typing import List, Optional


class CarrierNotConfigured(Exception):
    """Raised by a real adapter when its API key/contract isn't set in .env.
    The registry catches this and falls back to the mock adapter."""


class TrackingEventData:
    def __init__(self, status: str, note: Optional[str], timestamp: datetime, source: str):
        self.status = status
        self.note = note
        self.timestamp = timestamp
        self.source = source


class CarrierAdapter(ABC):
    name: str = "unknown"

    @abstractmethod
    async def create_shipment(self, booking) -> str:
        """Registers the shipment with the external network and returns its tracking number."""
        raise NotImplementedError

    @abstractmethod
    async def get_tracking_events(
        self, tracking_number: str, booking_created_at: datetime
    ) -> List[TrackingEventData]:
        """Returns the external network's view of this shipment's status history."""
        raise NotImplementedError
