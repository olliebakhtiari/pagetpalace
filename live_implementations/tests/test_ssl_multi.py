# Python standard.
import unittest

# Local.
from src.oanda_account import OandaAccount
from live_implementations.ssl_multi_time_frame import SSLMultiTimeFrame


class TestSSLMulti(unittest.TestCase):
    """ EXAMPLE TRADE OBJECT.
            [{
                    'id': '5',
                    'instrument': 'SPX500_USD',
                    'price': '3061.0',
                    'openTime': '2020-05-29T20:40:51.685944939Z',
                    'initialUnits': '1',
                    'initialMarginRequired': '123.8700',
                    'state': 'OPEN',
                    'currentUnits': '1',
                    'realizedPL': '0.0000',
                    'financing': '-0.5813',
                    'dividendAdjustment': '0.0000',
                    'unrealizedPL': '-0.7324',
                    'marginUsed': '123.8950',
                    'takeProfitOrder': {
                        'id': '6',
                        'createTime': '2020-05-29T20:40:51.685944939Z',
                        'type': 'TAKE_PROFIT',
                        'tradeID': '5',
                        'price': '3161.0',
                        'timeInForce': 'GTC',
                        'triggerCondition': 'DEFAULT',
                        'state': 'PENDING'
                    },
                    'stopLossOrder': {
                        'id': '7',
                        'createTime': '2020-05-29T20:40:51.685944939Z',
                        'type': 'STOP_LOSS',
                        'tradeID': '5',
                        'price': '2961.0',
                        'timeInForce': 'GTC',
                        'triggerCondition': 'DEFAULT',
                        'state': 'PENDING'
                    }
                }]
            """
    def setUp(self):
        self.s = SSLMultiTimeFrame(
            OandaAccount(account_id='', access_token='', account_type='')
        )

    def test_check_and_adjust_stops(self):
        pass

    def test_check_and_partially_close(self):
        pass

    def test_sync_pending_orders(self):
        pass

    def test_clean_local_lists(self):
        pass

    def test_get_unit_size_per_trade(self):
        pass

    def test_check_pct_hit(self):
        pass

    def test_calculate_new_sl_price(self):
        pass

    def test_get_valid_margin_size(self):
        pass

    def test_add_id_to_pending_orders(self):
        pass

    def test_convert_gbp_to_max_num_units(self):
        pass


if __name__ == '__main__':
    unittest.main()
