from sqlalchemy.orm import Session

from app.models.credit_ledger import CreditLedgerEntry
from app.models.user import User


def can_afford(user: User, cost: int) -> bool:
    """Whether this action may go ahead.

    Every caller asks through here rather than comparing `ai_credits`
    itself, so that an account exempt from charging is exempt everywhere.
    There were eight separate `user.ai_credits < COST` comparisons across
    the services and routers, and an exemption honoured by seven of them is
    not an exemption — it is a bug that only shows up on the eighth feature
    somebody tries.
    """
    return user.unlimited_credits or user.ai_credits >= cost


def adjust_credits(db: Session, user: User, action: str, amount: int) -> User:
    """Grant (amount > 0) or spend (amount < 0) credits, writing an audit row.

    Caller is responsible for the surrounding db.commit(). Raises ValueError
    if a spend would take the balance negative — check before calling for a
    friendlier error message where that matters.
    """
    # An exempt account still gets a ledger row, at zero. The balance is not
    # the point of the ledger; knowing what the account did is, and a silent
    # return here would make those accounts invisible in any usage review.
    if user.unlimited_credits and amount < 0:
        db.add(CreditLedgerEntry(user_id=user.id, action=action, amount=0, balance_after=user.ai_credits))
        return user

    new_balance = user.ai_credits + amount
    if new_balance < 0:
        raise ValueError("Insufficient credits")

    user.ai_credits = new_balance
    db.add(CreditLedgerEntry(user_id=user.id, action=action, amount=amount, balance_after=new_balance))
    return user
