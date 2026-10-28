"""Tests for the personal retention endpoint and the global auto-delete limit."""

from backend.components.models.audio_settings_model import AudioSettingsModel

URL = "/api/v1/settings/my-retention/"
AUDIO = "/api/v1/settings/audio-settings/"


def _set_global(session_factory, enabled=True, days=90):
    with session_factory() as session:
        session.add(
            AudioSettingsModel(auto_delete_enabled=enabled, auto_delete_days=days)
        )
        session.commit()


def test_user_sets_and_clears_a_shorter_period(
    client, create_user, auth_headers, session_factory
):
    _set_global(session_factory, days=90)
    headers = auth_headers(create_user("dr.mueller"))

    saved = client.put(URL, json={"personal_days": 30}, headers=headers)
    assert saved.status_code == 200
    assert saved.json() == {
        "personal_days": 30,
        "global_enabled": True,
        "global_days": 90,
    }

    cleared = client.put(URL, json={"personal_days": None}, headers=headers)
    assert cleared.json()["personal_days"] is None
    assert client.get(URL, headers=headers).json()["personal_days"] is None


def test_period_longer_than_global_limit_is_rejected(
    client, create_user, auth_headers, session_factory
):
    _set_global(session_factory, days=90)
    headers = auth_headers(create_user("dr.mueller"))

    response = client.put(URL, json={"personal_days": 120}, headers=headers)

    assert response.status_code == 400
    assert response.json()["detail"]["code"] == "retention_exceeds_global"


def test_any_period_allowed_when_global_limit_is_off(
    client, create_user, auth_headers, session_factory
):
    _set_global(session_factory, enabled=False, days=90)
    headers = auth_headers(create_user("dr.mueller"))

    assert (
        client.put(URL, json={"personal_days": 400}, headers=headers).status_code == 200
    )
    assert (
        client.put(URL, json={"personal_days": 0}, headers=headers).status_code == 422
    )


def test_audio_settings_validate_auto_delete_days(client, create_user, auth_headers):
    headers = auth_headers(create_user("admin1", role="admin"))
    payload = client.get(AUDIO, headers=headers).json()

    payload.update(auto_delete_enabled=True, auto_delete_days=0)
    rejected = client.put(AUDIO, json=payload, headers=headers)
    payload.update(auto_delete_days=180)
    accepted = client.put(AUDIO, json=payload, headers=headers)

    assert rejected.status_code == 422
    assert rejected.json()["detail"]["code"] == "auto_delete_days_invalid"
    assert accepted.status_code == 200
    assert accepted.json()["auto_delete_days"] == 180
