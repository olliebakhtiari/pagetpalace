# Python standard.
import unittest

# Local.
from src.oanda_account import OandaAccount
from live_implementations.ssl_multi_time_frame import SSLMultiTimeFrame


class TestSSLMulti(unittest.TestCase):
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

    def test_calculate_new_price(self):
        pass

    def test_get_valid_margin_size(self):
        pass

    def test_add_id_to_pending_orders(self):
        pass

    def test_convert_gbp_to_max_num_units(self):
        pass


if __name__ == '__main__':
    unittest.main()
