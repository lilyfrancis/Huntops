"""Working out which market a listing belongs to from its own location text.

A mailbox carries a market label and every job imported through it inherited
that label outright. That holds only while one mailbox receives one country's
alerts, and it often cannot: LinkedIn sends every saved search to the single
address on the account, so one forwarded stream carries Lagos, London and
Toronto roles together. Under the old rule all three became whatever the
mailbox said, and a user in Canada got Nigerian jobs in their feed.

So the listing's own location decides where it can, and the mailbox label
stays as the fallback for listings that do not say.

Ambiguity is real — London is in Ontario as well as England, Birmingham is in
Alabama as well as the West Midlands — so the checks run strongest first: an
explicit country, then a province or state code, then the city. "London, ON"
reaches the province rule before the city rule and lands in Canada; a bare
"London" falls through to the city rule and lands in the UK, which is the
right guess when nothing else is said.
"""

import re

# Explicit and unambiguous: a listing naming the country is not guessing.
_COUNTRY_ALIASES: dict[str, tuple[str, ...]] = {
    "Nigeria": ("nigeria",),
    "Canada": ("canada",),
    "USA": ("usa", "u.s.a", "united states", "us", "u.s", "america"),
    "UK": ("uk", "u.k", "united kingdom", "england", "scotland", "wales",
           "northern ireland", "great britain", "britain"),
    "UAE": ("uae", "u.a.e", "united arab emirates", "emirates"),
}

# Region codes settle the cities that exist in more than one country.
_REGION_CODES: dict[str, tuple[str, ...]] = {
    "Canada": ("on", "qc", "bc", "ab", "mb", "sk", "ns", "nb", "nl", "pe", "yt", "nt", "nu",
               "ontario", "quebec", "british columbia", "alberta", "manitoba", "saskatchewan",
               "nova scotia", "new brunswick", "newfoundland"),
    "USA": ("al", "ak", "az", "ar", "ca", "co", "ct", "de", "fl", "ga", "hi", "id", "il", "in",
            "ia", "ks", "ky", "la", "me", "md", "ma", "mi", "mn", "ms", "mo", "mt", "ne", "nv",
            "nh", "nj", "nm", "ny", "nc", "nd", "oh", "ok", "or", "pa", "ri", "sc", "sd", "tn",
            "tx", "ut", "vt", "va", "wa", "wv", "wi", "wy", "dc"),
}

# Weakest signal, so checked last.
_CITY_ALIASES: dict[str, tuple[str, ...]] = {
    "Nigeria": ("lagos", "abuja", "port harcourt", "ibadan", "kano", "benin city",
                "enugu", "abeokuta", "kaduna", "ikeja", "lekki", "victoria island"),
    "Canada": ("toronto", "vancouver", "montreal", "montréal", "calgary", "ottawa",
               "edmonton", "winnipeg", "halifax", "mississauga", "brampton", "hamilton",
               "kitchener", "waterloo", "victoria bc"),
    "USA": ("new york", "nyc", "san francisco", "los angeles", "chicago", "austin",
            "seattle", "boston", "atlanta", "denver", "dallas", "houston", "miami",
            "philadelphia", "phoenix", "san diego", "san jose", "washington dc",
            "silicon valley", "bay area"),
    "UK": ("london", "manchester", "birmingham", "leeds", "glasgow", "edinburgh",
           "bristol", "liverpool", "sheffield", "cardiff", "belfast", "newcastle",
           "nottingham", "reading uk", "cambridge uk", "oxford uk"),
    "UAE": ("dubai", "abu dhabi", "sharjah", "ajman", "ras al khaimah", "fujairah",
            "al ain", "jebel ali"),
}


def _compile(aliases: dict[str, tuple[str, ...]]) -> list[tuple[str, re.Pattern]]:
    """Word-bounded so "us" does not match inside Columbus, and dots escaped
    so "u.s" is not a wildcard.

    The alternation must be wrapped in a group: alternation binds looser than
    the lookarounds, so `(?<!x)a|b|c(?!y)` bounds only the first and last
    branches and every term between them matches mid-word. That let Alberta's
    "ab" match "Abu Dhabi".
    """
    compiled = []
    for market, terms in aliases.items():
        pattern = "|".join(re.escape(term) for term in sorted(terms, key=len, reverse=True))
        compiled.append((market, re.compile(rf"(?<![\w.])(?:{pattern})(?![\w])", re.I)))
    return compiled


_COUNTRY_PATTERNS = _compile(_COUNTRY_ALIASES)
_REGION_PATTERNS = _compile(_REGION_CODES)
_CITY_PATTERNS = _compile(_CITY_ALIASES)


def canonical_market(text: str | None) -> str | None:
    """The canonical market a piece of location text points at, or None.

    None means "no idea", not "nowhere" — the caller keeps its own default
    rather than inventing a market from a listing that never named one.
    """
    if not text or not text.strip():
        return None

    for patterns in (_COUNTRY_PATTERNS, _REGION_PATTERNS, _CITY_PATTERNS):
        for market, pattern in patterns:
            if pattern.search(text):
                return market
    return None


def resolve_market(location: str | None, known_markets: list[str]) -> str | None:
    """Which of the operator's own market labels this location belongs to.

    Returns the operator's spelling, not the canonical one: somebody who
    labelled their Gulf mailbox "Dubai" gets "Dubai" back for a job in Abu
    Dhabi, because that label is what their users picked at signup and what
    every existing job in that market is already tagged with. Introducing
    "UAE" alongside it would quietly split one market into two.
    """
    target = canonical_market(location)
    if target is None:
        return None

    for market in known_markets:
        if canonical_market(market) == target:
            return market
    return None
