# Python standard.
import unittest

# Local.
from src.oanda_account import Account
from live_implementations.ssl_multi_time_frame import SSLMultiTimeFrame


class TestSSLMulti(unittest.TestCase):
    def setUp(self):
        self.s = SSLMultiTimeFrame(
            Account(account_id='DEMO_V20_ACCOUNT_NUMBER', access_token='DEMO_ACCESS_TOKEN', account_type='DEMO_API')
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

    def test_calculate_new_price(self):
        pass

    def test_get_valid_margin_size(self):
        pass

    def test_add_id_to_pending_orders(self):
        pass


if __name__ == '__main__':
    unittest.main()
