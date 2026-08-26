"""Constants for the Thames Water integration."""

DOMAIN = "thames_water"

CONF_EMAIL = "email"
CONF_PASSWORD = "password"
CONF_ACCOUNT_NUMBER = "account_number"

DEFAULT_SCAN_INTERVAL = 30  # minutes

BASE_URL = "https://myaccount.thameswater.co.uk"
LOGIN_HOST = "https://login.thameswater.co.uk"

USAGE_PATH = "/mydashboard/my-meters-usage"
GET_METERS_PATH = "/ajax/waterMeter/getMeters"
GET_CONSUMPTION_PATH = "/ajax/waterMeter/getSmartWaterMeterConsumptions"

USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0 Safari/537.36"
)

# OAuth / Azure AD B2C identifiers
B2C_CLIENT_ID = "049f19f2-7f22-4973-a805-74958744ec81"
B2C_TENANT_PATH = "/identity.thameswater.co.uk/B2C_1_ORAM_Prod_SignIn"
B2C_POLICY = "B2C_1_ORAM_Prod_SignIn"
B2C_API = "CombinedSigninAndSignup"
