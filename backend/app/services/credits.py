from sqlalchemy.orm import Session

from app.models.credit_ledger import CreditLedgerEntry
from app.models.user import User


def adjust_credits(db: Session, user: User, action: str, amount: int) -> User:
    """Grant (amount > 0) or spend (amount < 0) credits, writing an audit row.

    Caller is responsible for the surrounding db.commit(). Raises ValueError
    if a spend would take the balance negative — check before calling for a
    friendlier error message where that matters.
    """
    new_balance = user.ai_credits + amount
    if new_balance < 0:
        raise ValueError("Insufficient credits")

    user.ai_credits = new_balance
    db.add(CreditLedgerEntry(user_id=user.id, action=action, amount=amount, balance_after=new_balance))
    return user
