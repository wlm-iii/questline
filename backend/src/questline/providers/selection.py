from questline.config import Settings
from questline.providers.errors import ProviderUnavailable
from questline.providers.extractor import Extractor, FakeExtractor
from questline.providers.gemini_extractor import GeminiExtractor
from questline.providers.google_maps import GoogleMaps, MapsUnavailable
from questline.providers.maps import FakeMaps, MapsProvider


def extractor_for_settings(settings: Settings) -> Extractor:
    if settings.planner_provider == "fake":
        return FakeExtractor()
    if settings.gemini_api_key is None or not settings.gemini_model:
        raise ProviderUnavailable("Gemini extraction requires GEMINI_API_KEY and GEMINI_MODEL")
    return GeminiExtractor(settings.gemini_api_key.get_secret_value(), settings.gemini_model)


def maps_for_settings(settings: Settings) -> MapsProvider:
    if settings.maps_provider == "fake":
        return FakeMaps()
    if settings.google_maps_api_key is None:
        raise MapsUnavailable("Google Maps requires GOOGLE_MAPS_API_KEY")
    return GoogleMaps(settings.google_maps_api_key.get_secret_value())
