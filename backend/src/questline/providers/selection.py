from questline.config import Settings
from questline.providers.errors import ProviderUnavailable
from questline.providers.extractor import Extractor, FakeExtractor
from questline.providers.gemini_extractor import GeminiExtractor
from questline.providers.gemini_selector import GeminiSelector
from questline.providers.google_maps import GoogleMaps, MapsUnavailable
from questline.providers.maps import FakeMaps, MapsProvider
from questline.providers.planner import Planner, QuestlinePlanner
from questline.providers.routes import EstimateRouter, GoogleRoutes, Router
from questline.services.suggestions import SuggestionSink


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


def router_for_settings(settings: Settings) -> Router:
    if settings.maps_provider == "fake":
        return EstimateRouter()
    if settings.google_maps_api_key is None:
        raise MapsUnavailable("Google Maps requires GOOGLE_MAPS_API_KEY")
    return GoogleRoutes(settings.google_maps_api_key.get_secret_value())


def planner_for_settings(
    settings: Settings, *, register_suggestions: SuggestionSink | None = None
) -> Planner:
    """Fake mode picks by votes offline; Gemini mode adds AI picks and reasons."""
    router = router_for_settings(settings)
    selector = None
    if settings.planner_provider == "gemini":
        if settings.gemini_api_key is None or not settings.gemini_model:
            raise ProviderUnavailable("Gemini planning requires GEMINI_API_KEY and GEMINI_MODEL")
        selector = GeminiSelector(settings.gemini_api_key.get_secret_value(), settings.gemini_model)
    return QuestlinePlanner(
        router,
        selector,
        maps=maps_for_settings(settings),
        register_suggestions=register_suggestions,
        detour_limit=settings.planner_detour_limit,
        suggestion_queries=settings.planner_suggestion_query_limit,
        suggestion_limit=settings.planner_suggestion_limit,
    )
