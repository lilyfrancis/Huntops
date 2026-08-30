import logging

from cryptography.fernet import Fernet

from app.core.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

_fernet: Fernet | None = None


def _get_fernet() -> Fernet:
    global _fernet
    if _fernet is None:
        if settings.TOKEN_ENCRYPTION_KEY:
            _fernet = Fernet(settings.TOKEN_ENCRYPTION_KEY.encode())
        else:
            logger.warning(
                "TOKEN_ENCRYPTION_KEY not set — generating an ephemeral key for this process. "
                "OAuth tokens encrypted with it will NOT decrypt after a restart. Set a real key "
                "(Fernet.generate_key()) before storing real Gmail connections."
            )
            _fernet = Fernet(Fernet.generate_key())
    return _fernet


def encrypt(value: str) -> str:
    return _get_fernet().encrypt(value.encode()).decode()


def decrypt(value: str) -> str:
    return _get_fernet().decrypt(value.encode()).decode()
