"""ASR backends follow the settings: a reloaded settings row rebuilds them."""

from backend.components.models.settings_model import WhisperSettingsModel
from backend.components.services import asr_factory


def _settings(endpoint):
    return WhisperSettingsModel(final_api_endpoint=endpoint, final_api_model="m")


def test_backend_is_reused_while_settings_are_unchanged(monkeypatch):
    settings = _settings("http://a:9000")
    monkeypatch.setattr(asr_factory, "get_settings", lambda: settings)
    factory = asr_factory.ASRFactory()
    assert factory.get_final_backend() is factory.get_final_backend()


def test_backend_is_rebuilt_when_the_settings_object_is_reloaded(monkeypatch):
    """Another instance changed the endpoint; our cache reloaded after its TTL."""
    current = {"s": _settings("http://old:9000")}
    monkeypatch.setattr(asr_factory, "get_settings", lambda: current["s"])
    factory = asr_factory.ASRFactory()
    assert "old" in factory.get_final_backend().endpoint

    current["s"] = _settings("http://new:9000")

    assert "new" in factory.get_final_backend().endpoint


def test_reset_backends_still_forces_a_rebuild(monkeypatch):
    settings = _settings("http://a:9000")
    monkeypatch.setattr(asr_factory, "get_settings", lambda: settings)
    factory = asr_factory.ASRFactory()
    first = factory.get_final_backend()
    factory.reset_backends()
    assert factory.get_final_backend() is not first
