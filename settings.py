# Local.
from pagetpalace.tools import get_config_dict_from_s3

PAGETPALACELIVE = get_config_dict_from_s3('pagetpalacelive.json')
PAGETPALACEDEMO = get_config_dict_from_s3('pagetpalacedemo.json')

LIVE_V20_ACCOUNT_NUMBER = PAGETPALACELIVE['V20_ACCOUNT_NUMBER']
LIVE_ACCESS_TOKEN = PAGETPALACELIVE['ACCESS_TOKEN']

DEMO_V20_ACCOUNT_NUMBER = PAGETPALACEDEMO['V20_ACCOUNT_NUMBER']
DEMO_ACCESS_TOKEN = PAGETPALACEDEMO['ACCESS_TOKEN']

PROTOCOL = 'https://'
OANDA_API_VERSION = 'v3'
OANDA_DOMAINS = {
    'LIVE_STREAM': 'stream-fxtrade.oanda.com',
    'DEMO_STREAM': 'stream-fxpractice.oanda.com',
    'LIVE_API': 'api-fxtrade.oanda.com',
    'DEMO_API': 'api-fxpractice.oanda.com',
}
