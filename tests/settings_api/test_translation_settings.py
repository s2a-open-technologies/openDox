"""Translation is an operator decision: off by default, then all or selected users.

The target language is the instance's transcription language
(WhisperSettingsModel.language), never a separate setting, and it can never be
offered as a dictation language to translate from.
"""

from sqlmodel import select

from backend.components.models.audit_model import AuditEvent
from backend.components.models.llm_settings_model import LlmSettingsModel
from backend.components.models.settings_model import WhisperSettingsModel
from backend.components.models.user_model import User

URL = "/api/v1/settings/translation/"
ME_URL = "/api/v1/settings/translation/me"


def _config(**overrides):
    config = {"enabled": True, "access": "selected", "languages": ["ru", "ar"]}
    config.update(overrides)
    return config


def _set_language(session_factory, language: str) -> None:
    with session_factory() as session:
        session.add(WhisperSettingsModel(language=language))
        session.commit()


def _release(session_factory, user_id: int) -> None:
    with session_factory() as session:
        user = session.get(User, user_id)
        user.translation_allowed = True
        session.add(user)
        session.commit()


def test_off_by_default_for_everyone(client, create_user, auth_headers):
    user = create_user("dr.a")

    body = client.get(ME_URL, headers=auth_headers(user)).json()

    assert body == {
        "available": False,
        "languages": [],
        "target_language": "de",
        "live_languages": [],
    }


def test_selected_access_needs_the_per_user_release(
    client, create_user, auth_headers, session_factory
):
    admin = create_user("admin", role="admin")
    user = create_user("dr.a")
    assert (
        client.put(URL, json=_config(), headers=auth_headers(admin)).status_code == 200
    )

    assert client.get(ME_URL, headers=auth_headers(user)).json()["available"] is False

    _release(session_factory, user.id)
    body = client.get(ME_URL, headers=auth_headers(user)).json()
    assert body == {
        "available": True,
        "languages": ["ru", "ar"],
        "target_language": "de",
        "live_languages": ["ru"],
    }


def test_access_all_releases_everyone(client, create_user, auth_headers):
    admin = create_user("admin", role="admin")
    user = create_user("dr.a")
    client.put(URL, json=_config(access="all"), headers=auth_headers(admin))

    assert client.get(ME_URL, headers=auth_headers(user)).json()["available"] is True


def test_unavailable_while_llm_is_off(
    client, create_user, auth_headers, session_factory
):
    admin = create_user("admin", role="admin")
    user = create_user("dr.a")
    client.put(URL, json=_config(access="all"), headers=auth_headers(admin))
    with session_factory() as session:
        session.add(LlmSettingsModel(llm_enabled=False))
        session.commit()

    assert client.get(ME_URL, headers=auth_headers(user)).json()["available"] is False


def test_target_follows_the_instance_language(
    client, create_user, auth_headers, session_factory
):
    _set_language(session_factory, "en")
    admin = create_user("admin", role="admin")
    user = create_user("dr.a")
    client.put(
        URL,
        json=_config(access="all", languages=["ru", "de"]),
        headers=auth_headers(admin),
    )

    body = client.get(ME_URL, headers=auth_headers(user)).json()

    assert body["target_language"] == "en"
    assert body["languages"] == ["ru", "de"]


def test_target_language_cannot_be_a_source(client, create_user, auth_headers):
    admin = create_user("admin", role="admin")

    response = client.put(
        URL, json=_config(languages=["ru", "DE"]), headers=auth_headers(admin)
    )

    assert response.status_code == 400
    assert response.json()["detail"]["code"] == "translation_target_in_sources"


def test_invalid_language_code_is_rejected(client, create_user, auth_headers):
    admin = create_user("admin", role="admin")

    response = client.put(
        URL, json=_config(languages=["russisch"]), headers=auth_headers(admin)
    )

    assert response.status_code == 400
    assert response.json()["detail"]["code"] == "invalid_language_code"


def test_only_admins_save_and_the_save_is_audited(
    client, create_user, auth_headers, session_factory
):
    admin = create_user("admin", role="admin")
    moderator = create_user("mod", role="moderator")

    assert (
        client.put(URL, json=_config(), headers=auth_headers(moderator)).status_code
        == 403
    )
    assert client.get(URL, headers=auth_headers(moderator)).status_code == 403
    response = client.put(
        URL, json=_config(languages=[" RU ", "ru", "ar"]), headers=auth_headers(admin)
    )

    assert response.status_code == 200
    assert response.json()["languages"] == ["ru", "ar"]
    with session_factory() as session:
        events = session.exec(
            select(AuditEvent).where(AuditEvent.action == "settings.translation.update")
        ).all()
        assert len(events) == 1


def test_user_management_sets_the_release_and_audits_it(
    client, create_user, auth_headers, session_factory
):
    admin = create_user("admin", role="admin")
    user = create_user("dr.a")

    response = client.put(
        f"/api/v1/auth/users/{user.id}",
        json={"translation_allowed": True},
        headers=auth_headers(admin),
    )

    assert response.status_code == 200
    assert response.json()["translation_allowed"] is True
    with session_factory() as session:
        event = session.exec(
            select(AuditEvent).where(AuditEvent.action == "user.update")
        ).one()
        assert event.details["fields"] == ["translation_allowed"]
