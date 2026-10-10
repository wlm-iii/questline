from questline.config import Settings
from questline.providers.google_maps import GoogleMaps, MapsUnavailable
from questline.providers.maps import FakeMaps, MapsProvider


def maps_for_settings(settings: Settings) -> MapsProvider:
    if settings.maps_provider == "fake":
        return FakeMaps()
    if settings.google_maps_api_key is None:
        raise MapsUnavailable("Google Maps requires GOOGLE_MAPS_API_KEY")
    return GoogleMaps(settings.google_maps_api_key.get_secret_value())
