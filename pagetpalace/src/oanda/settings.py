# Local.
from pagetpalace.tools import get_config_dict_from_s3

PAGETPALACELIVE = get_config_dict_from_s3('pagetpalacelive.json')
LIVE_ACCESS_TOKEN = PAGETPALACELIVE['CBB_ACCESS_TOKEN']

PROTOCOL = 'https://'
OANDA_API_VERSION = 'v3'
OANDA_DOMAINS = {
    'LIVE_STREAM': 'stream-fxtrade.oanda.com',
    'DEMO_STREAM': 'stream-fxpractice.oanda.com',
    'LIVE_API': 'api-fxtrade.oanda.com',
    'DEMO_API': 'api-fxpractice.oanda.com',
}
