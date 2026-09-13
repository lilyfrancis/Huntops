"""Live integration checks. "The string is non-empty" was never the question."""

from unittest.mock import MagicMock, patch

from app.services import integration_checks
from tests.test_alert_mailboxes import _make_admin


def test_an_unset_key_reports_what_stops_working(monkeypatch):
    """Not just "not configured" — which feature goes dark, so the operator
    can decide whether they care."""
    monkeypatch.setattr(integration_checks.settings, "APOLLO_API_KEY", "")
    result = integration_checks.check_apollo()

    assert result.configured is False
    assert result.ok is None  # nothing to test, not a failure
    assert "hiring contact" in result.detail


def test_an_unset_smtp_says_the_failure_is_silent(monkeypatch):
    monkeypatch.setattr(integration_checks.settings, "SMTP_HOST", "")
    assert "silently" in integration_checks.check_smtp().detail


def test_apollo_403_names_the_master_key_trap(monkeypatch):
    """The specific failure people lose an afternoon to: a normal Apollo key
    works everywhere except people search."""
    monkeypatch.setattr(integration_checks.settings, "APOLLO_API_KEY", "k")
    with patch("app.services.integration_checks.httpx.post",
               return_value=MagicMock(status_code=403, text="forbidden")):
        result = integration_checks.check_apollo()

    assert result.ok is False
    assert "master" in result.detail.lower()


def test_apollo_success_reports_what_came_back(monkeypatch):
    monkeypatch.setattr(integration_checks.settings, "APOLLO_API_KEY", "k")
    with patch("app.services.integration_checks.httpx.post",
               return_value=MagicMock(status_code=200, json=lambda: {"people": [{"id": "p1"}]})):
        result = integration_checks.check_apollo()

    assert result.ok is True
    assert "1 result" in result.detail


def test_paystack_catches_a_plan_code_that_does_not_exist(monkeypatch):
    """A typo here takes payment for a plan nobody can buy, and the key itself
    tests fine."""
    monkeypatch.setattr(integration_checks.settings, "PAYSTACK_SECRET_KEY", "sk")
    monkeypatch.setattr(integration_checks.settings, "PAYSTACK_PLAN_PRO", "PLN_typo")
    monkeypatch.setattr(integration_checks.settings, "PAYSTACK_PLAN_ELITE", "PLN_real")
    with patch("app.services.integration_checks.httpx.get",
               return_value=MagicMock(status_code=200, json=lambda: {"data": [{"plan_code": "PLN_real"}]})):
        result = integration_checks.check_paystack()

    assert result.ok is False
    assert "PLN_typo" in result.detail


def test_paystack_passes_when_both_plans_exist(monkeypatch):
    monkeypatch.setattr(integration_checks.settings, "PAYSTACK_SECRET_KEY", "sk")
    monkeypatch.setattr(integration_checks.settings, "PAYSTACK_PLAN_PRO", "PLN_pro")
    monkeypatch.setattr(integration_checks.settings, "PAYSTACK_PLAN_ELITE", "PLN_elite")
    with patch("app.services.integration_checks.httpx.get",
               return_value=MagicMock(status_code=200,
                                      json=lambda: {"data": [{"plan_code": "PLN_pro"}, {"plan_code": "PLN_elite"}]})):
        assert integration_checks.check_paystack().ok is True


def test_an_anthropic_auth_failure_says_what_to_do(monkeypatch):
    monkeypatch.setattr(integration_checks.settings, "ANTHROPIC_API_KEY", "bad")
    with patch("anthropic.Anthropic") as mock_client:
        mock_client.return_value.messages.create.side_effect = Exception(
            "Error code: 401 - {'type': 'authentication_error'}"
        )
        result = integration_checks.check_anthropic()

    assert result.ok is False
    assert "Generate a new one" in result.detail


def test_a_crashing_check_does_not_take_the_page_down(monkeypatch):
    with patch.dict(integration_checks.CHECKS, {"apollo": lambda: 1 / 0}):
        results = {r.name: r for r in integration_checks.run_all()}

    assert results["apollo"].ok is False
    assert len(results) == len(integration_checks.CHECKS)


# ---------- the admin endpoints ----------

def test_integration_status_requires_admin(client):
    from tests.conftest import auth_headers, register_user

    data = register_user(client, email="not-admin-integrations@example.com")
    assert client.get("/api/admin/integrations", headers=auth_headers(data["access_token"])).status_code == 403


def test_integration_status_lists_every_check(client):
    headers = _make_admin(client, email="integrations-admin@example.com")
    resp = client.get("/api/admin/integrations", headers=headers)

    assert resp.status_code == 200
    assert {r["name"] for r in resp.json()} == set(integration_checks.CHECKS)


def test_testing_one_integration(client, monkeypatch):
    headers = _make_admin(client, email="one-integration-admin@example.com")
    monkeypatch.setattr(integration_checks.settings, "SMTP_HOST", "")

    resp = client.post("/api/admin/integrations/smtp/test", headers=headers)
    assert resp.status_code == 200
    assert resp.json()["configured"] is False


def test_an_unknown_integration_is_a_404(client):
    headers = _make_admin(client, email="unknown-integration-admin@example.com")
    assert client.post("/api/admin/integrations/nope/test", headers=headers).status_code == 404


def test_paystack_catches_a_currency_that_disagrees_with_the_plans(monkeypatch):
    """BILLING_CURRENCY only drives display; the card is charged whatever the
    plan says. Set differently, the site advertises $7,500 and Paystack bills
    ₦7,500, and nothing else anywhere notices."""
    monkeypatch.setattr(integration_checks.settings, "PAYSTACK_SECRET_KEY", "sk")
    monkeypatch.setattr(integration_checks.settings, "PAYSTACK_PLAN_PRO", "PLN_pro")
    monkeypatch.setattr(integration_checks.settings, "PAYSTACK_PLAN_ELITE", "PLN_elite")
    monkeypatch.setattr(integration_checks.settings, "BILLING_CURRENCY", "USD")

    with patch("app.services.integration_checks.httpx.get", return_value=MagicMock(
        status_code=200,
        json=lambda: {"data": [
            {"plan_code": "PLN_pro", "currency": "NGN"},
            {"plan_code": "PLN_elite", "currency": "NGN"},
        ]},
    )):
        result = integration_checks.check_paystack()

    assert result.ok is False
    assert "NGN" in result.detail and "USD" in result.detail


def test_matching_currencies_pass(monkeypatch):
    monkeypatch.setattr(integration_checks.settings, "PAYSTACK_SECRET_KEY", "sk")
    monkeypatch.setattr(integration_checks.settings, "PAYSTACK_PLAN_PRO", "PLN_pro")
    monkeypatch.setattr(integration_checks.settings, "PAYSTACK_PLAN_ELITE", "PLN_elite")
    monkeypatch.setattr(integration_checks.settings, "BILLING_CURRENCY", "ngn")  # case shouldn't matter

    with patch("app.services.integration_checks.httpx.get", return_value=MagicMock(
        status_code=200,
        json=lambda: {"data": [
            {"plan_code": "PLN_pro", "currency": "NGN"},
            {"plan_code": "PLN_elite", "currency": "NGN"},
        ]},
    )):
        assert integration_checks.check_paystack().ok is True


def _configure_whatsapp(monkeypatch, base, number_id="699182519954320"):
    from app.services import whatsapp

    for mod in (integration_checks, whatsapp):
        monkeypatch.setattr(mod.settings, "WHATSAPP_API_BASE", base)
        monkeypatch.setattr(mod.settings, "WHATSAPP_PHONE_NUMBER_ID", number_id)
        monkeypatch.setattr(mod.settings, "WHATSAPP_ACCESS_TOKEN", "tok")


def test_a_failing_whatsapp_check_says_which_url_it_called(monkeypatch):
    """Meta's "Unknown path components" quotes the path it received but not
    the host, so the same message appears whether the base URL is wrong, the
    version is doubled, or the ID belongs to another provider. Printing the
    URL we actually sent is what separates them."""
    _configure_whatsapp(monkeypatch, "https://wapi.bexos.cloud")

    response = MagicMock(status_code=400)
    response.text = (
        '{"error":{"message":"Unknown path components: \\/v21.0\\/699182519954320",'
        '"type":"OAuthException","code":2500}}'
    )
    with patch("app.services.integration_checks.httpx.get", return_value=response):
        result = integration_checks.check_whatsapp()

    assert result.ok is False
    assert "https://wapi.bexos.cloud/v21.0/699182519954320" in result.detail
    assert "host alone" in result.detail


def test_a_version_left_on_the_base_is_not_sent_twice(monkeypatch):
    """The URL reported back must be the one actually requested, including
    the stripping — otherwise the diagnostic lies about what was sent."""
    _configure_whatsapp(monkeypatch, "https://graph.facebook.com/v25.0")

    with patch("app.services.integration_checks.httpx.get", return_value=MagicMock(status_code=401)) as get:
        result = integration_checks.check_whatsapp()

    assert get.call_args.args[0] == "https://graph.facebook.com/v21.0/699182519954320"
    assert "v25.0" not in result.detail
