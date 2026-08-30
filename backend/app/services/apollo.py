"""Apollo.io recruiter discovery — ported from Job Engine Phase 3.

Two gotchas Job Engine's spec documents from hard experience, both still
true here: search results obfuscate the last name (e.g. "Li***a"), so
enrichment must key on the person's `id`, never on the masked name; and the
work email lands in `person.email`, not the `personal_emails` array (which
is usually empty for a work contact).
"""

import re

import httpx

from app.core.config import get_settings

settings = get_settings()

SEARCH_URL = "https://api.apollo.io/api/v1/mixed_people/api_search"
MATCH_URL = "https://api.apollo.io/api/v1/people/match"
HTTP_TIMEOUT = 15.0

_RECRUITER_TITLE_PATTERN = re.compile(r"recruit|talent|people ops|human resources|\bhr\b|hiring|acquisition", re.I)


class ApolloAPIError(Exception):
    pass


def _headers() -> dict:
    if not settings.APOLLO_API_KEY:
        raise ApolloAPIError("APOLLO_API_KEY is not configured")
    return {"X-Api-Key": settings.APOLLO_API_KEY, "Content-Type": "application/json"}


def search_people(company_name: str) -> list[dict]:
    resp = httpx.post(
        SEARCH_URL,
        headers=_headers(),
        json={
            "q_organization_name": company_name,
            "person_titles": settings.recruiter_titles_list,
            "page": 1,
            "per_page": 5,
        },
        timeout=HTTP_TIMEOUT,
    )
    if resp.status_code >= 400:
        raise ApolloAPIError(f"Apollo search failed ({resp.status_code}): {resp.text[:500]}")
    return resp.json().get("people", [])


def pick_best_candidate(people: list[dict]) -> dict | None:
    if not people:
        return None
    for person in people:
        if _RECRUITER_TITLE_PATTERN.search(person.get("title", "") or ""):
            return person
    return people[0]


def enrich_person(apollo_person_id: str) -> dict:
    """Reveal a work email for a previously-found person. Costs an Apollo credit."""
    resp = httpx.post(
        MATCH_URL,
        headers=_headers(),
        json={"id": apollo_person_id, "reveal_personal_emails": True},
        timeout=HTTP_TIMEOUT,
    )
    if resp.status_code >= 400:
        raise ApolloAPIError(f"Apollo enrichment failed ({resp.status_code}): {resp.text[:500]}")
    return resp.json().get("person", {})
