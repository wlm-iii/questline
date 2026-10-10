from pathlib import Path

import pytest
from pydantic import ValidationError

from questline.integrations.imessage.settings import RelaySettings


def test_reads_the_spec_env_names(monkeypatch):
    monkeypatch.setenv("QUESTLINE_API_URL", "https://api.questline.test")
    monkeypatch.setenv("API_TOKEN", "relay-token")
    monkeypatch.setenv("WEB_BASE_URL", "https://questline.test")
    monkeypatch.setenv("RELAY_STATE_PATH", "/tmp/relay.json")
    monkeypatch.setenv("RELAY_FLUSH_SECONDS", "5")
    settings = RelaySettings(_env_file=None)
    assert settings.questline_api_url == "https://api.questline.test"
    assert settings.api_token.get_secret_value() == "relay-token"
    assert settings.relay_state_path == Path("/tmp/relay.json")
    assert (settings.imsg_bin, settings.relay_flush_seconds, settings.relay_flush_max) == (
        "imsg",
        5,
        20,
    )


def test_api_url_and_token_are_required(monkeypatch):
    for name in ("QUESTLINE_API_URL", "API_TOKEN", "WEB_BASE_URL"):
        monkeypatch.delenv(name, raising=False)
    with pytest.raises(ValidationError):
        RelaySettings(_env_file=None)
