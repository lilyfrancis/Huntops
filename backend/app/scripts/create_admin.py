"""Create or promote an admin account.

Admins can't self-register — the role is rejected at /api/auth/register on
purpose — so the very first one has to be made here, with shell access to the
box. That matters more than it used to: the entire supply side now runs
through admin-connected alert mailboxes, so until an admin exists there is
nobody who can give the product any jobs.

    python -m app.scripts.create_admin ops@huntops.site --name "Ops Admin"

The password is read from the terminal without echoing rather than taken as an
argument, so it never lands in shell history or the process list.
"""

import argparse
import getpass
import sys

from app.core.security import hash_password, validate_password_strength
from app.db.base import SessionLocal
from app.models.enums import UserRole
from app.models.user import User


def main() -> int:
    parser = argparse.ArgumentParser(description="Create or promote a HuntOps admin.")
    parser.add_argument("email")
    parser.add_argument("--name", default="Administrator")
    args = parser.parse_args()

    db = SessionLocal()
    try:
        user = db.query(User).filter(User.email == args.email).first()

        if user is not None:
            if user.role == UserRole.admin:
                print(f"{args.email} is already an admin.")
                return 0
            # Promoting an existing account is the common case in practice:
            # the operator signs up through the UI, then runs this.
            user.role = UserRole.admin
            user.is_approved = True
            user.is_suspended = False
            db.commit()
            print(f"Promoted {args.email} to admin.")
            return 0

        password = getpass.getpass("Password: ")
        if password != getpass.getpass("Confirm password: "):
            print("Passwords do not match.", file=sys.stderr)
            return 1

        try:
            validate_password_strength(password)
        except Exception as e:  # HTTPException carries the reason in .detail
            print(getattr(e, "detail", str(e)), file=sys.stderr)
            return 1

        db.add(User(
            email=args.email,
            password_hash=hash_password(password),
            full_name=args.name,
            role=UserRole.admin,
            is_approved=True,
            ai_credits=0,
        ))
        db.commit()
        print(f"Created admin {args.email}.")
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
