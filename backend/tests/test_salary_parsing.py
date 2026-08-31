import pytest

from app.services.salary_parsing import parse_salary


@pytest.mark.parametrize(
    "text,currency,annual_min,annual_max",
    [
        ("$120,000–$150,000", "USD", 120_000, 150_000),
        ("$120,000-$150,000", "USD", 120_000, 150_000),
        ("£45,000 – £60,000", "GBP", 45_000, 60_000),
        ("$50k - $70k", "USD", 50_000, 70_000),
        ("€60000", "EUR", 60_000, 60_000),
        ("USD 90,000 to 110,000", "USD", 90_000, 110_000),
        ("₦500,000 per month", "NGN", 6_000_000, 6_000_000),
        ("NGN 500,000 - 800,000 per month", "NGN", 6_000_000, 9_600_000),
        ("$25/hour", "USD", 52_000, 52_000),
        ("£350 per day", "GBP", 91_000, 91_000),
    ],
)
def test_parses_real_world_salary_strings(text, currency, annual_min, annual_max):
    parsed = parse_salary(text)
    assert parsed is not None, text
    assert parsed["currency"] == currency
    assert parsed["annual_min"] == pytest.approx(annual_min)
    assert parsed["annual_max"] == pytest.approx(annual_max)


@pytest.mark.parametrize(
    "text",
    [
        None,
        "",
        "   ",
        "Competitive",
        "Depending on experience",
        "Negotiable salary",
    ],
)
def test_unparseable_strings_yield_nothing_rather_than_a_guess(text):
    assert parse_salary(text) is None


def test_implausible_figures_are_rejected():
    """A number that annualizes outside human pay means we misread the string."""
    assert parse_salary("$12 - $15") is None  # too low to be annual, no period given
    assert parse_salary("Ref 2024 posting") is None  # a year, not a salary


def test_european_thousands_separator_is_not_read_as_decimals():
    parsed = parse_salary("€65.000 per year")
    assert parsed is not None
    assert parsed["annual_min"] == pytest.approx(65_000)


def test_monthly_pay_is_annualized_for_comparison():
    parsed = parse_salary("$8,000 per month")
    assert parsed["period"] == "month"
    assert parsed["min"] == 8_000  # raw figure preserved
    assert parsed["annual_min"] == pytest.approx(96_000)  # annualized for benchmarks


def test_missing_currency_is_reported_as_none_not_assumed():
    parsed = parse_salary("90,000 - 120,000")
    assert parsed is not None
    assert parsed["currency"] is None


def test_single_figure_sets_min_and_max_equal():
    parsed = parse_salary("$100,000")
    assert parsed["annual_min"] == parsed["annual_max"] == 100_000


def test_numbers_are_ordered_regardless_of_string_order():
    parsed = parse_salary("$150,000 down from $120,000")
    assert parsed["annual_min"] == 120_000
    assert parsed["annual_max"] == 150_000
