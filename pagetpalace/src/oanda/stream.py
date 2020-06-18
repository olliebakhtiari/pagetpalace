# Python standard.
import json
from optparse import OptionParser

# Third-party.
import requests

# Local.
from pagetpalace.src.oanda.settings import OANDA_DOMAINS


class OandaStream:
    def __init__(self, account_type: str, auth_token: str, account_id: str, instrument: str, stream_data: str):
        self.auth_token = auth_token
        self.account_id = account_id
        self.account_type = account_type
        self.instrument = instrument  # e.g. "EUR_USD,USD_JPY,..."
        self.stream_data = stream_data  # ask/bid, candles, account_latest_candles, order_book, position_book.

    def __repr__(self):
        return f'<DataStream(instrument={self.instrument}, stream_data={self.stream_data})>'

    def __str__(self):
        return f'account: {self.account_id}... streaming: {self.instrument}'

    def connect_to_stream(self):
        """ https://developer.oanda.com/rest-live-v20/pricing-ep/

        :return:
        """
        domain_dict = {
            'live_stream': OANDA_DOMAINS['LIVE_STREAM'],
            'demo_stream': OANDA_DOMAINS['DEMO_STREAM'],
            'live_api': OANDA_DOMAINS['LIVE_API'],
            'demo_api': OANDA_DOMAINS['DEMO_API'],
        }
        environment = self.account_type
        domain = domain_dict[environment]
        access_token = self.auth_token
        account_id = self.account_id
        instrument = self.instrument
        urls = {
            'ask/bid': f'https://{domain}/v3/accounts/{account_id}/pricing/stream',
            'candles': f'https://{domain}/v3/instruments/{instrument}/candles',
            'account_latest_candles': f'https://{domain}/v3/accounts/{account_id}/candles/latest',
            'order_book': f'https://{domain}/v3/instruments/{instrument}/orderBook',
            'position_book': f'https://{domain}/v3/instruments/{instrument}/positionBook',
        }
        try:
            s = requests.Session()
            url = urls[self.stream_data]
            headers = {
                'Authorization': f'Bearer {access_token}',
                'X-Accept-Datetime-Format': 'unix',
            }
            params = {
                'instruments': instrument,
                'accountId': account_id,
            }
            req = requests.Request('GET', url, headers=headers, params=params)
            pre = req.prepare()
            resp = s.send(pre, stream=True, verify=True)
            return resp
        except Exception as exc:
            s.close()
            print(f'Caught exception when connecting to stream\n {str(exc)}')

    def get_stream(self, display_heartbeat):
        response = self.connect_to_stream()
        if response.status_code != 200:
            print(response.text)
            return False
        for line in response.iter_lines(1):
            if line:
                try:
                    line = line.decode('utf-8')
                    msg = json.loads(line)
                except Exception as e:
                    print(f'Caught exception when converting message into json\n {str(e)}')
                    return False
                if 'instrument' in msg or 'tick' in msg or display_heartbeat:
                    print(line)

    def execute(self):
        usage = "usage: %prog [options]"
        parser = OptionParser(usage)
        parser.add_option(
            "-b",
            "--displayHeartBeat",
            dest="verbose",
            action="store_true",
            help="Display HeartBeat in streaming data",
        )
        display_heartbeat = False
        (options, args) = parser.parse_args()
        if len(args) > 1:
            parser.error("incorrect number of arguments")
        if options.verbose:
            display_heartbeat = True
        self.get_stream(display_heartbeat)
