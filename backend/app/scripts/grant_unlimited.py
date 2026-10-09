"""Exempt an account from credit charging, and put it on Elite.

For the operator's own accounts. They have to be able to use the product
without buying from themselves, and support has to be able to reproduce a
paid flow without spending somebody's balance.

    python -m app.scripts.grant_unlimited you@example.com another@example.com

Idempotent, and it only ever grants — rerunning changes nothing. To take the
exemption away again:

    python -m app.scripts.grant_unlimited you@example.com --revoke

The account must already exist: this does not create one, because an account
made here would have no password the person knows. Sign up through the site
first, then run this.
"""

import argparse
import sys

from app.db.base import SessionLocal
from app.models.enums import SubscriptionTier, UserRole
from app.models.user import User


def main() -> int:
    parser = argparse.ArgumentParser(description="Grant or revoke unlimited credits on an account.")
    parser.add_argument("emails", nargs="+")
    parser.add_argument("--revoke", action="store_true", help="Take the exemption away again.")
    args = parser.parse_args()

    db = SessionLocal()
    missing: list[str] = []
    try:
        for email in args.emails:
            user = db.query(User).filter(User.email == email).first()
            if user is None:
                missing.append(email)
                continue

            if args.revoke:
                user.unlimited_credits = False
                print(f"Revoked unlimited credits for {email} (tier left as {user.subscription_tier.value}).")
                continue

            user.unlimited_credits = True
            # Elite as well as the exemption: the exemption removes the cost,
            # not the tier, and a couple of capabilities still read the tier.
            if user.role == UserRole.job_seeker:
                user.subscription_tier = SubscriptionTier.elite
            print(f"{email}: unlimited credits, tier {user.subscription_tier.value}.")

        db.commit()
    finally:
        db.close()

    if missing:
        print(
            "\nNo account for: " + ", ".join(missing) +
            "\nSign up at the site with that address first, then run this again.",
            file=sys.stderr,
        )
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
