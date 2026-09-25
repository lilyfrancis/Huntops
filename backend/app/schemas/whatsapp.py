from datetime import datetime

from pydantic import BaseModel


class WhatsAppConnectionOut(BaseModel):
    """Everything the profile page needs to say what is and is not working.

    Four states, and the UI has to tell them apart: the operator has not set
    WhatsApp up at all, the user has saved no number, the user has a number
    but has never messaged us (so nothing will ever arrive), and the whole
    thing is live.
    """

    configured: bool
    business_number: str | None
    opt_in_url: str | None
    number_on_file: str | None
    opted_in: bool
    opted_in_at: datetime | None
