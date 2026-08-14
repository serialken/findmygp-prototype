from app.config import get_settings
from app.services.carriers.base import CarrierAdapter
from app.services.carriers.chronopost_adapter import ChronopostAdapter
from app.services.carriers.colissimo_adapter import ColissimoAdapter
from app.services.carriers.dhl_adapter import DHLAdapter
from app.services.carriers.mock_adapter import MockCarrierAdapter

settings = get_settings()

_mock = MockCarrierAdapter()
_real_adapters = {
    "chronopost": ChronopostAdapter(),
    "colissimo": ColissimoAdapter(),
    "dhl": DHLAdapter(),
}
_configured_flags = {
    "chronopost": bool(settings.chronopost_api_key),
    "colissimo": bool(settings.colissimo_api_key),
    "dhl": bool(settings.dhl_api_key),
}


def get_adapter(external_network: str) -> CarrierAdapter:
    """Returns the real adapter for `external_network` if its API key is
    configured in .env, otherwise falls back to the mock/simulation adapter.
    This is the single place that decides real-vs-mock — nothing else in
    the app needs to know or care which one it's talking to."""
    if external_network in _real_adapters and _configured_flags.get(external_network):
        return _real_adapters[external_network]
    return _mock
