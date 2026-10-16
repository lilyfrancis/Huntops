"""Where a person can actually work, and which listings that admits.

`Job.market` says where a listing's supply came from — which alert mailbox,
or nothing at all for the global API boards. That is a fact about provenance,
and the feed was filtering on it as though it were a fact about eligibility.
The two are not the same, and the difference is the whole of what a job
seeker means when they pick a country.

Somebody in Lagos asking for Nigerian work means "roles I am allowed to
apply for from Nigeria". That includes a fully remote role at a Dutch
company that accepts applicants from anywhere, and a remote role advertised
for EMEA. It excludes a role whose listing says US citizens only, however
remote it is. None of that is knowable from `market`.

This module holds the country vocabulary that makes the second reading
possible, and builds the one SQL clause that expresses it.
"""

import re

from sqlalchemy import and_, or_
from sqlalchemy.sql.elements import BooleanClauseList

from app.models.job import Job

# Canonical name -> the strings a board might write for it.
#
# Aliases are matched as substrings against the free-text location, so a
# two-letter code is not safe to list here: "%ng%" matches half the dictionary.
# Codes are handled by the restriction regexes below instead, where a word
# boundary is available.
COUNTRY_ALIASES: dict[str, tuple[str, ...]] = {
    "Nigeria": ("nigeria", "nigerian", "lagos", "abuja", "ibadan", "port harcourt"),
    "Ghana": ("ghana", "accra", "kumasi"),
    "Kenya": ("kenya", "nairobi", "mombasa"),
    "South Africa": ("south africa", "johannesburg", "cape town", "durban", "pretoria"),
    "Egypt": ("egypt", "cairo", "alexandria"),
    "US": ("united states", "usa", "u.s.a", "u.s.", "america", "new york", "san francisco",
           "austin", "chicago", "seattle", "boston", "atlanta", "denver", "los angeles"),
    "Canada": ("canada", "canadian", "toronto", "vancouver", "montreal", "calgary", "ottawa"),
    "UK": ("united kingdom", "england", "scotland", "wales", "london", "manchester",
           "birmingham", "leeds", "glasgow", "edinburgh", "bristol"),
    "Ireland": ("ireland", "dublin", "cork"),
    "Germany": ("germany", "deutschland", "berlin", "munich", "münchen", "hamburg", "frankfurt"),
    "Netherlands": ("netherlands", "holland", "amsterdam", "rotterdam", "utrecht"),
    "France": ("france", "paris", "lyon", "marseille"),
    "Spain": ("spain", "españa", "madrid", "barcelona", "valencia"),
    "Portugal": ("portugal", "lisbon", "lisboa", "porto"),
    "Poland": ("poland", "polska", "warsaw", "warszawa", "kraków", "krakow", "wrocław"),
    "UAE": ("united arab emirates", "dubai", "abu dhabi", "sharjah"),
    "India": ("india", "bangalore", "bengaluru", "mumbai", "delhi", "hyderabad", "pune"),
    "Australia": ("australia", "sydney", "melbourne", "brisbane", "perth"),
    "Singapore": ("singapore",),
    "Philippines": ("philippines", "manila", "cebu"),
    "Brazil": ("brazil", "brasil", "são paulo", "sao paulo", "rio de janeiro"),
    "Mexico": ("mexico", "méxico", "mexico city", "guadalajara", "monterrey"),
}

# What this product offers in the picker, busiest supply first. A person's
# eligibility is a fact about them, not about our stock, so this is the
# curated list rather than a query — unlike markets, which must never promise
# a country with no mailbox behind it.
ELIGIBILITY_OPTIONS: tuple[str, ...] = (
    "Nigeria", "Ghana", "Kenya", "South Africa", "Egypt",
    "US", "Canada", "UK", "Ireland", "Germany", "Netherlands", "France",
    "Spain", "Portugal", "Poland", "UAE", "India", "Australia",
    "Singapore", "Philippines", "Brazil", "Mexico",
)

# A restriction wider than a country still admits the people inside it. A
# remote role advertised for EMEA is open to somebody in Lagos; one
# advertised for the US is not, and the point of the whole filter is that it
# can tell those two apart.
REGION_MEMBERS: dict[str, frozenset[str]] = {
    "Africa": frozenset({"Nigeria", "Ghana", "Kenya", "South Africa", "Egypt"}),
    "EU": frozenset({"Ireland", "Germany", "Netherlands", "France", "Spain", "Portugal", "Poland"}),
    "Europe": frozenset({"UK", "Ireland", "Germany", "Netherlands", "France", "Spain",
                         "Portugal", "Poland"}),
    "EMEA": frozenset({"Nigeria", "Ghana", "Kenya", "South Africa", "Egypt", "UK", "Ireland",
                       "Germany", "Netherlands", "France", "Spain", "Portugal", "Poland", "UAE"}),
    "North America": frozenset({"US", "Canada"}),
    "LATAM": frozenset({"Brazil", "Mexico"}),
    "APAC": frozenset({"India", "Australia", "Singapore", "Philippines"}),
}

# Everything we recognise as a place, for `canonical`.
_LOOKUP: dict[str, str] = {}
for _name, _aliases in COUNTRY_ALIASES.items():
    _LOOKUP[_name.lower()] = _name
    for _alias in _aliases:
        _LOOKUP[_alias] = _name
for _region in REGION_MEMBERS:
    _LOOKUP[_region.lower()] = _region
_LOOKUP.update({
    "uk": "UK", "gb": "UK", "gbr": "UK", "great britain": "UK",
    "us": "US", "u.s.": "US", "us only": "US", "usa only": "US",
    "ca": "Canada", "ng": "Nigeria", "de": "Germany", "nl": "Netherlands",
    "ae": "UAE", "za": "South Africa", "ie": "Ireland",
    "emea": "EMEA", "apac": "APAC", "latam": "LATAM", "eu": "EU",
})



def canonical(value: str | None) -> str | None:
    """The canonical name for a place, or None if the string names none.

    A place found anywhere in the string wins over the open-to-anyone words,
    because boards combine the two constantly: "Remote - Canada" and
    "Anywhere in Europe" both state a restriction, and reading the first word
    and stopping would turn each of them into "open to everybody".

    None for "Worldwide" and its synonyms on their own. Those are the
    *absence* of a restriction, which is a different thing from a place, and
    returning one for them would turn "open to everyone" into "open to
    nowhere".
    """
    if not value:
        return None
    text = value.strip().lower().rstrip(".")
    if not text:
        return None

    if text in _LOOKUP:
        return _LOOKUP[text]
    # "USA, Canada" and "Remote - Nigeria" both arrive as one string; take the
    # first place named in it rather than giving up on the whole field.
    for part in re.split(r"[,/|;()\-\u2013]| or ", text):
        part = part.strip()
        if part and part in _LOOKUP:
            return _LOOKUP[part]
    # Long aliases only. A two- or three-letter code as a substring matches
    # half the dictionary, and this runs against free text.
    for alias, name in _LOOKUP.items():
        if len(alias) >= 5 and alias in text:
            return name
    return None


def admits(restriction: str | None, country: str) -> bool:
    """Whether a listing restricted to `restriction` is open to `country`.

    No restriction admits everybody: that is what null means on the column.
    """
    if restriction is None:
        return True
    place = canonical(restriction) or restriction
    if place == country:
        return True
    return country in REGION_MEMBERS.get(place, frozenset())


def allowed_restrictions(countries: set[str]) -> set[str]:
    """Every `restricted_to` value these countries' residents may apply under."""
    allowed = set(countries)
    for region, members in REGION_MEMBERS.items():
        if members & countries:
            allowed.add(region)
    return allowed


def eligibility_clause(countries: list[str]) -> BooleanClauseList | None:
    """Jobs somebody in one of these countries can actually apply for.

    Three ways a listing qualifies, and a job needs only one:

    1. It names a restriction these people fall inside — "Canada", "EMEA".
    2. It is remote with no restriction detected, i.e. open from anywhere.
    3. It is physically in one of these countries, so they are already there.

    None when nothing recognisable was asked for, which the caller must read
    as "no narrowing" — a typo in a country name must not empty the feed.

    A listing both located in Lagos *and* marked US-only is a contradiction
    between two heuristics, and this resolves it by showing the job. Hiding a
    real role is the costlier mistake; a wrong one can be scrolled past.
    """
    chosen = {c for c in (canonical(value) for value in countries) if c}
    if not chosen:
        return None

    clauses = [
        Job.restricted_to.in_(sorted(allowed_restrictions(chosen))),
        and_(Job.restricted_to.is_(None), Job.is_remote.is_(True)),
    ]
    for country in sorted(chosen):
        clauses.extend(
            Job.location.ilike(f"%{alias}%") for alias in COUNTRY_ALIASES.get(country, ())
        )
    return or_(*clauses)
