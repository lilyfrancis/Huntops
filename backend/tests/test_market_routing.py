"""Which market a job lands in when one mailbox carries several countries.

LinkedIn sends every saved search to the single address on the account, so an
operator running five markets cannot have it deliver each country to its own
mailbox. One forwarded stream arrives carrying all of them, and tagging every
job with the mailbox's own label would put Lagos roles in a Canadian feed.
"""

from unittest.mock import patch

import pytest

from app.models.job import Job
from app.services import alert_mailboxes
from app.services.imap_client import FetchedMessage
from app.services.markets import canonical_market, resolve_market
from app.schemas.ai import ExtractedJobPosting
from tests.test_alert_mailboxes import LINKEDIN, _seed_mailbox, _sync


# ---------- reading a location ----------

@pytest.mark.parametrize("location,expected", [
    ("Lagos, Nigeria", "Nigeria"),
    ("Toronto, ON", "Canada"),
    ("Dubai", "UAE"),
    ("Abu Dhabi", "UAE"),
    ("New York, NY", "USA"),
    ("Port Harcourt", "Nigeria"),
    ("Victoria Island, Lagos", "Nigeria"),
])
def test_an_unambiguous_location_is_read_correctly(location, expected):
    assert canonical_market(location) == expected


@pytest.mark.parametrize("location,expected", [
    # A country beats everything.
    ("London, United Kingdom", "UK"),
    ("London, Canada", "Canada"),
    # Then a province or state code.
    ("London, ON", "Canada"),
    ("Birmingham, AL", "USA"),
    ("Manchester, NH", "USA"),
    # With neither, the city's best-known home.
    ("London", "UK"),
    ("Birmingham", "UK"),
    ("Manchester", "UK"),
])
def test_a_city_in_two_countries_is_settled_by_the_strongest_signal(location, expected):
    """London is in Ontario as well as England. The checks run country, then
    region code, then city, so the more specific text always wins."""
    assert canonical_market(location) == expected


@pytest.mark.parametrize("location", ["Remote", "Anywhere", "", None, "Hybrid", "EMEA"])
def test_a_location_that_names_nowhere_returns_nothing(location):
    """None means "no idea", not "nowhere" — the caller keeps its own default
    rather than inventing a market."""
    assert canonical_market(location) is None


def test_a_substring_is_not_a_match():
    """"us" inside Columbus and "ab" inside Abu Dhabi both matched before the
    alternation was grouped, so Abu Dhabi was read as Alberta."""
    assert canonical_market("Columbus, OH") == "USA"      # from OH, not from "us"
    assert canonical_market("Abu Dhabi") == "UAE"         # not Alberta
    assert canonical_market("Columbus") is None           # nothing else to go on


# ---------- mapping onto the operator's own labels ----------

def test_it_answers_with_the_operators_spelling_not_the_canonical_one():
    """Someone who labelled their Gulf mailbox "Dubai" must keep getting
    "Dubai" — their users picked that at signup and every existing job is
    tagged with it. Answering "UAE" would split one market in two."""
    assert resolve_market("Abu Dhabi", ["Canada", "Dubai", "UK"]) == "Dubai"
    assert resolve_market("Sharjah", ["Canada", "UAE"]) == "UAE"


def test_a_market_the_operator_does_not_run_is_not_invented():
    """A German job arriving in a Canadian mailbox must not create a market
    nobody can select at signup."""
    assert resolve_market("Berlin, Germany", ["Canada", "UK"]) is None
    assert resolve_market("Lagos, Nigeria", ["Canada", "UK"]) is None


# ---------- end to end through a sync ----------

def test_one_mailbox_carrying_four_countries_routes_each_job_correctly(db_session):
    """The case this exists for: a single forwarded LinkedIn stream."""
    for market in ("Nigeria", "UK", "USA"):
        _seed_mailbox(db_session, market=market)
    mailbox = _seed_mailbox(db_session, market="Canada")

    summary = _sync(
        db_session, mailbox,
        messages=[FetchedMessage(uid=1, sender=LINKEDIN, body="alert text")],
        postings=[
            ExtractedJobPosting(title="Backend Engineer", company="A", url="https://x.test/1", location="Lagos, Nigeria"),
            ExtractedJobPosting(title="Product Manager", company="B", url="https://x.test/2", location="London, UK"),
            ExtractedJobPosting(title="Account Executive", company="C", url="https://x.test/3", location="Austin, TX"),
            ExtractedJobPosting(title="Design Lead", company="D", url="https://x.test/4", location="Toronto, ON"),
        ],
    )

    assert summary["inserted"] == 4
    by_title = {j.title: j.market for j in db_session.query(Job).all()}
    assert by_title == {
        "Backend Engineer": "Nigeria",
        "Product Manager": "UK",
        "Account Executive": "USA",
        "Design Lead": "Canada",
    }


def test_a_listing_with_no_usable_location_keeps_the_mailbox_market(db_session):
    """The fallback still matters — which is why one mailbox per market is
    still the right setup, not one shared mailbox for everything."""
    mailbox = _seed_mailbox(db_session, market="Canada")
    _sync(
        db_session, mailbox,
        messages=[FetchedMessage(uid=1, sender=LINKEDIN, body="alert text")],
        postings=[ExtractedJobPosting(title="Ops Manager", company="A", url="https://x.test/9", location="Remote")],
    )

    assert db_session.query(Job).one().market == "Canada"


def test_a_country_with_no_mailbox_falls_back_rather_than_vanishing(db_session):
    """A stray German listing stays visible under the mailbox's market rather
    than being tagged into a market with no mailbox, which nobody could
    select and so nobody would ever see."""
    mailbox = _seed_mailbox(db_session, market="UK")
    _sync(
        db_session, mailbox,
        messages=[FetchedMessage(uid=1, sender=LINKEDIN, body="alert text")],
        postings=[ExtractedJobPosting(title="Data Engineer", company="A", url="https://x.test/8", location="Berlin, Germany")],
    )

    assert db_session.query(Job).one().market == "UK"
