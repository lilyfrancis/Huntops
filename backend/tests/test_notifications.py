from unittest.mock import MagicMock, patch

from app.services import notifications


@patch("app.services.notifications.settings")
def test_send_email_skips_when_smtp_not_configured(mock_settings):
    mock_settings.SMTP_HOST = ""
    assert notifications.send_email("user@example.com", "Subject", "Body") is False


@patch("app.services.notifications.smtplib.SMTP")
@patch("app.services.notifications.settings")
def test_send_email_sends_via_smtp(mock_settings, mock_smtp_class):
    mock_settings.SMTP_HOST = "smtp.example.com"
    mock_settings.SMTP_PORT = 587
    mock_settings.SMTP_USE_TLS = True
    mock_settings.SMTP_USERNAME = "user"
    mock_settings.SMTP_PASSWORD = "pass"
    mock_settings.SMTP_FROM_EMAIL = "noreply@huntops.app"

    mock_server = MagicMock()
    mock_smtp_class.return_value.__enter__.return_value = mock_server

    result = notifications.send_email("user@example.com", "Subject", "Body")

    assert result is True
    mock_server.starttls.assert_called_once()
    mock_server.login.assert_called_once_with("user", "pass")
    mock_server.sendmail.assert_called_once()


@patch("app.services.notifications.smtplib.SMTP")
@patch("app.services.notifications.settings")
def test_send_email_returns_false_on_smtp_error(mock_settings, mock_smtp_class):
    import smtplib

    mock_settings.SMTP_HOST = "smtp.example.com"
    mock_settings.SMTP_USERNAME = ""
    mock_smtp_class.side_effect = smtplib.SMTPException("connection refused")

    assert notifications.send_email("user@example.com", "Subject", "Body") is False


@patch("app.services.notifications.send_email", return_value=True)
@patch("app.services.notifications.settings")
def test_alert_admin_uses_configured_address(mock_settings, mock_send):
    mock_settings.ADMIN_ALERT_EMAIL = "admin@huntops.app"
    notifications.alert_admin("Something broke", "details here")
    mock_send.assert_called_once()
    assert mock_send.call_args[0][0] == "admin@huntops.app"
    assert "Something broke" in mock_send.call_args[0][1]


@patch("app.services.notifications.send_email")
@patch("app.services.notifications.settings")
def test_alert_admin_noop_without_configured_address(mock_settings, mock_send):
    mock_settings.ADMIN_ALERT_EMAIL = ""
    notifications.alert_admin("Something broke", "details")
    mock_send.assert_not_called()
