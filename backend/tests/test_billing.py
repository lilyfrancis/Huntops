import uuid

from unittest.mock import MagicMock, patch

from app.db.base import SessionLocal
from app.models.enums import SubscriptionTier
from app.services import billing as billing_service
from tests.conftest import register_user


def test_checkout_completed_upgrades_tier_and_grants_credits(client):
    data = register_user(client, email="billing@example.com")
    user_id = uuid.UUID(data["user"]["id"])

    session = SessionLocal()
    try:
        from app.models.user import User

        user = session.get(User, user_id)
        assert user.ai_credits == 10  # signup bonus only, so far

        event_data = {
            "metadata": {"user_id": str(user_id), "tier": "pro"},
            "subscription": "sub_123",
        }
        billing_service.handle_checkout_completed(session, event_data)

        session.refresh(user)
        assert user.subscription_tier == SubscriptionTier.pro
        assert user.stripe_subscription_id == "sub_123"
        assert user.ai_credits == 10 + 100  # signup bonus + Pro grant
    finally:
        session.close()


def test_subscription_deleted_downgrades_to_free(client):
    data = register_user(client, email="cancel@example.com")
    user_id = uuid.UUID(data["user"]["id"])

    session = SessionLocal()
    try:
        from app.models.user import User

        user = session.get(User, user_id)
        user.stripe_customer_id = "cus_abc"
        user.subscription_tier = SubscriptionTier.elite
        session.commit()

        billing_service.handle_subscription_deleted(session, {"customer": "cus_abc"})

        session.refresh(user)
        assert user.subscription_tier == SubscriptionTier.free
        assert user.stripe_subscription_id is None
    finally:
        session.close()


@patch("app.services.billing.stripe.Customer.create")
@patch("app.services.billing.stripe.checkout.Session.create")
def test_create_checkout_session_creates_stripe_customer_once(mock_session_create, mock_customer_create, client):
    mock_customer_create.return_value = MagicMock(id="cus_new")
    mock_session_create.return_value = MagicMock(url="https://checkout.stripe.com/test")

    data = register_user(client, email="checkout@example.com")
    session = SessionLocal()
    try:
        from app.models.user import User

        user = session.get(User, uuid.UUID(data["user"]["id"]))

        url = billing_service.create_checkout_session(session, user, SubscriptionTier.pro)
        assert url == "https://checkout.stripe.com/test"
        assert user.stripe_customer_id == "cus_new"
        mock_customer_create.assert_called_once()

        # Second call reuses the existing Stripe customer instead of creating another.
        billing_service.create_checkout_session(session, user, SubscriptionTier.elite)
        mock_customer_create.assert_called_once()
    finally:
        session.close()
