"""Constants for the notiOne integration."""
from datetime import timedelta

DOMAIN = "notione"

TOKEN_URL = "https://auth.notinote.me/oauth/token"
LIST_URL = "https://api.notinote.me/secured/internal/devicelist"

# Shared credentials of the official notiOne mobile application, not user secrets.
OAUTH_CLIENT_ID = "test-oauth-client-id"
OAUTH_CLIENT_SECRET = "$2y$12$vXOUtEenVFCO1Zgy2YiePuF3WF/sDgNO3YnhRjl49NIDlEbGeSeOu"
OAUTH_SCOPE = "NOTI"

# The API rejects requests with default HTTP client user agents.
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/104.0.5112.102 Safari/537.36"
)

CONF_TRACKED_DEVICES = "tracked_devices"
DEFAULT_SCAN_INTERVAL = timedelta(seconds=300)
REQUEST_TIMEOUT = 30
