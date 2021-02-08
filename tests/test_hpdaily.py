# Python standard.
import unittest

# Local.
from pagetpalace.src.instruments import CurrencyPairs
from pagetpalace.src.oanda.account import OandaAccount
from pagetpalace.src.oanda.hpdaily import HPDaily
from pagetpalace.src.oanda.settings import DEMO_ACCOUNT_NUMBER, DEMO_ACCESS_TOKEN


class TestHPDaily(unittest.TestCase):
    def setUp(self):
        self.hp_daily = HPDaily(
            account=OandaAccount(DEMO_ACCESS_TOKEN, DEMO_ACCOUNT_NUMBER, 'DEMO_API'),
            instrument=CurrencyPairs.GBP_USD,
            boundary_multipliers={},
            trade_multipliers={},
            coefficients={},
        )
        self.hp_daily._latest_data = {}

    def test_is_long_signal(self):
        pass

    def test_is_short_signal(self):
        pass

    def test_get_s1_signal(self):
        pass

    def test_get_stop_loss_pip_amount(self):
        pass


if __name__ == '__main__':
    unittest.main()
