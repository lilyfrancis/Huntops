from unittest.mock import MagicMock, patch

import pytest

from app.services import apollo


def test_pick_best_candidate_prefers_recruiter_titles():
    people = [
        {"id": "1", "name": "A", "title": "Software Engineer"},
        {"id": "2", "name": "B", "title": "Senior Technical Recruiter"},
    ]
    assert apollo.pick_best_candidate(people)["id"] == "2"


def test_pick_best_candidate_falls_back_to_first_when_no_recruiter_titled():
    people = [{"id": "1", "name": "A", "title": "Software Engineer"}]
    assert apollo.pick_best_candidate(people)["id"] == "1"


def test_pick_best_candidate_empty_list_returns_none():
    assert apollo.pick_best_candidate([]) is None


@patch("app.services.apollo.settings")
def test_search_people_raises_without_api_key(mock_settings):
    mock_settings.APOLLO_API_KEY = ""
    with pytest.raises(apollo.ApolloAPIError):
        apollo.search_people("Acme")


@patch("app.services.apollo.httpx.post")
def test_search_people_uses_id_not_masked_name(mock_post):
    # Apollo search obfuscates last names (e.g. "Li***a") — this only verifies
    # the search call is made and returns the raw people list untouched, since
    # enrichment (keyed on id) is what actually matters for correctness here.
    mock_post.return_value = MagicMock(status_code=200, json=lambda: {
        "people": [{"id": "abc123", "name": "Jane Li***a", "title": "Recruiter"}]
    })
    with patch("app.services.apollo.settings") as mock_settings:
        mock_settings.APOLLO_API_KEY = "fake-key"
        mock_settings.recruiter_titles_list = ["Recruiter"]
        people = apollo.search_people("Acme")

    assert people[0]["id"] == "abc123"


@patch("app.services.apollo.httpx.post")
def test_enrich_person_reads_email_field_not_personal_emails(mock_post):
    # The documented gotcha: work email is person.email, personal_emails is
    # usually empty for a work contact — this locks in reading the right field.
    mock_post.return_value = MagicMock(status_code=200, json=lambda: {
        "person": {"email": "jane@acme.com", "email_status": "verified", "personal_emails": []}
    })
    with patch("app.services.apollo.settings") as mock_settings:
        mock_settings.APOLLO_API_KEY = "fake-key"
        person = apollo.enrich_person("abc123")

    assert person["email"] == "jane@acme.com"


@patch("app.services.apollo.httpx.post")
def test_search_people_raises_on_http_error(mock_post):
    mock_post.return_value = MagicMock(status_code=403, text="Forbidden — not a master API key")
    with patch("app.services.apollo.settings") as mock_settings:
        mock_settings.APOLLO_API_KEY = "fake-key"
        mock_settings.recruiter_titles_list = ["Recruiter"]
        with pytest.raises(apollo.ApolloAPIError):
            apollo.search_people("Acme")
