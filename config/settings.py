# Python standard.
import os
import json

ROOT_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_FILE_LOCATION = os.path.abspath(f'{ROOT_DIR}/config.json')
with open(CONFIG_FILE_LOCATION, 'r') as read_file:
    CONFIG = json.load(read_file)

OANDA_LIVE_USERNAME = CONFIG['OANDA_LIVE_USERNAME']
OANDA_LIVE_V20_ACCOUNT_NUMBER = CONFIG['OANDA_LIVE_V20_ACCOUNT_NUMBER']
OANDA_LIVE_PASSWORD = CONFIG['OANDA_LIVE_PASSWORD']
OANDA_LIVE_ACCESS_TOKEN = CONFIG['OANDA_LIVE_ACCESS_TOKEN']

OANDA_DEMO_USERNAME = CONFIG['OANDA_DEMO_USERNAME']
OANDA_DEMO_V20_ACCOUNT_NUMBER = CONFIG['OANDA_DEMO_V20_ACCOUNT_NUMBER']
OANDA_DEMO_ACCESS_TOKEN = CONFIG['OANDA_DEMO_ACCESS_TOKEN']

OANDA_DOMAINS = {
    'LIVE_STREAM': 'stream-fxtrade.oanda.com',
    'DEMO_STREAM': 'stream-fxpractice.oanda.com',
    'LIVE_API': 'api-fxtrade.oanda.com',
    'DEMO_API': 'api-fxpractice.oanda.com',
}
