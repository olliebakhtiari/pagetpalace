# Local.
from pagetpalace.tools import get_config_dict_from_s3

_PAGETPALACELIVE = get_config_dict_from_s3('pagetpalacelive.json')
_PAGETPALACEDEMO = get_config_dict_from_s3('demo.json')

LIVE_ACCESS_TOKEN = _PAGETPALACELIVE['CBB_ACCESS_TOKEN']
DEMO_ACCESS_TOKEN = _PAGETPALACEDEMO['ACCESS_TOKEN']

# Live.
NAS_ACCOUNT_NUMBER = _PAGETPALACELIVE['CBB_NAS100_ACC_NUM']
SPX_ACCOUNT_NUMBER = _PAGETPALACELIVE['CBB_SPX500_ACC_NUM']
GBP_USD_ACCOUNT_NUMBER = _PAGETPALACELIVE['CBB_GBP_USD_ACC_NUM']

# Demo.
DEMO_ACCOUNT_NUMBER = _PAGETPALACEDEMO['V20_ACCOUNT_NUMBER']

PROTOCOL = 'https://'
OANDA_API_VERSION = 'v3'
OANDA_DOMAINS = {
    'LIVE_STREAM': 'stream-fxtrade.oanda.com',
    'DEMO_STREAM': 'stream-fxpractice.oanda.com',
    'LIVE_API': 'api-fxtrade.oanda.com',
    'DEMO_API': 'api-fxpractice.oanda.com',
}
