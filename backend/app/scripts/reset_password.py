"""Set a new password on an existing account.

Passwords are bcrypt hashes, so a forgotten one cannot be recovered — only
replaced. There is no self-service reset email yet, and the first admin is
created from the shell anyway, so this is the way back in.

    python -m app.scripts.reset_password admin@jobquick.site

The password is read from the terminal without echoing rather than taken as
an argument, so it never lands in shell history or the process list.
"""

import argparse
import getpass
import sys

from app.core.security import hash_password, validate_password_strength
from app.db.base import SessionLocal
from app.models.user import User


def main() -> int:
    parser = argparse.ArgumentParser(description="Reset an account's password.")
    parser.add_argument("email")
    args = parser.parse_args()

    db = SessionLocal()
    try:
        user = db.query(User).filter(User.email == args.email).first()
        if user is None:
            print(f"No account for {args.email}.", file=sys.stderr)
            return 1

        password = getpass.getpass("New password: ")
        if password != getpass.getpass("Confirm password: "):
            print("Passwords do not match.", file=sys.stderr)
            return 1

        try:
            validate_password_strength(password)
        except Exception as e:  # HTTPException carries the reason in .detail
            print(getattr(e, "detail", str(e)), file=sys.stderr)
            return 1

        user.password_hash = hash_password(password)
        # A reset is also how somebody locked out gets back in, so it lifts a
        # suspension that would otherwise make the new password useless.
        user.is_suspended = False
        db.commit()
        print(f"Password reset for {args.email} ({user.role.value}).")
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
