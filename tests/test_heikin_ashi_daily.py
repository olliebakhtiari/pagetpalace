# Python standard.
import unittest

# Third-party.
import pandas as pd

# Local.
from pagetpalace.src.instruments import Indices
from pagetpalace.src.oanda.account import OandaAccount
from pagetpalace.src.oanda.heikin_ashi_daily import HeikinAshiDaily
from pagetpalace.src.oanda.settings import DEMO_ACCOUNT_NUMBER, DEMO_ACCESS_TOKEN


class TestHPDaily(unittest.TestCase):
    def setUp(self):
        self.ha_d = HeikinAshiDaily(
            equity_split=3,
            account=OandaAccount(DEMO_ACCESS_TOKEN, DEMO_ACCOUNT_NUMBER, 'DEMO_API'),
            instrument=Indices.SPX500_USD,
            boundary_multipliers={'below': 0.01},
            trade_multipliers={'1': {'sl': 0.2, 'tp': 1}},
            ssma_period=4,
        )

    def test_get_signals_is_long(self):
        self.ha_d._latest_data = {'D': pd.read_csv('test_data/heikin_ashi_daily_long_signal.csv')}
        self.ha_d._strategy_atr_values = {}
        self.ha_d._strategy_ssma_values = {}
        self.assertEqual(self.ha_d._get_signals(), {'1': 'long'})

    def test_get_signals_is_short(self):
        self.ha_d._latest_data = {'D': pd.read_csv('test_data/heikin_ashi_daily_short_signal.csv')}
        self.ha_d._strategy_atr_values = {}
        self.ha_d._strategy_ssma_values = {}
        self.assertEqual(self.ha_d._get_signals(), {'1': 'short'})

    def test_get_stop_loss_pip_amount(self):
        self.ha_d._latest_data = {'D': pd.read_csv('test_data/heikin_ashi_daily_long_signal.csv')}
        self.ha_d._strategy_atr_values = {}
        self.assertEqual(self.ha_d._get_stop_loss_pip_amount(), 1)

    def test_place_pending_order_correctly(self):
        self.ha_d._latest_data = {'D': pd.read_csv('test_data/heikin_ashi_daily_place_order.csv')}
        self.ha_d._strategy_atr_values = {}
        self.ha_d._place_new_pending_order_if_units_available('1', 'long')


if __name__ == '__main__':
    unittest.main()
