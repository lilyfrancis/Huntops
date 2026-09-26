from unittest.mock import MagicMock, patch

from app.services import notifications


@patch("app.services.notifications.settings")
def test_send_email_skips_when_smtp_not_configured(mock_settings):
    mock_settings.SMTP_HOST = ""
    assert notifications.send_email("user@example.com", "Subject", "Body") is False


# The two tests that used to live here mocked smtplib itself, so they passed
# happily while the real client deadlocked against a TLS-only port. Sending
# is now covered in test_smtp_tls.py against actual servers on actual
# sockets, which is the only way a wire-protocol mismatch is visible.


@patch("app.services.notifications.send_email", return_value=True)
@patch("app.services.notifications.settings")
def test_alert_admin_uses_configured_address(mock_settings, mock_send):
    mock_settings.ADMIN_ALERT_EMAIL = "admin@jobquickai.site"
    notifications.alert_admin("Something broke", "details here")
    mock_send.assert_called_once()
    assert mock_send.call_args[0][0] == "admin@jobquickai.site"
    assert "Something broke" in mock_send.call_args[0][1]


@patch("app.services.notifications.send_email")
@patch("app.services.notifications.settings")
def test_alert_admin_noop_without_configured_address(mock_settings, mock_send):
    mock_settings.ADMIN_ALERT_EMAIL = ""
    notifications.alert_admin("Something broke", "details")
    mock_send.assert_not_called()
