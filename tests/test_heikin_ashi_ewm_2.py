# Python standard.
import unittest

# Third-party.
import pandas as pd

# Local.
from pagetpalace.src.oanda.instruments.instruments import Indices
from pagetpalace.src.oanda.account import OandaAccount
from pagetpalace.src.oanda.strategies.strategy_implementations.heikin_ashi_ewm_2 import HeikinAshiEwm2
from pagetpalace.src.oanda.settings import DEMO_ACCOUNT_NUMBER, DEMO_ACCESS_TOKEN


class TestHeikinAshiEwm2(unittest.TestCase):
    def setUp(self):
        self.ha_ewm = HeikinAshiEwm2(
            equity_split=3,
            account=OandaAccount(DEMO_ACCESS_TOKEN, DEMO_ACCOUNT_NUMBER, 'DEMO_API'),
            instrument=Indices.IN50_USD,
            boundary_multipliers={
                'D': {
                    'continuation': {'long': {'below': 1000, 'above': 2}},
                    'reverse': {'long': {'below': 0.5, 'above': 0.001}}
                }
            },
            trade_multipliers={'1': {'long': {'sl': 2, 'tp': 3}}},
            ewm_period=18,
        )

    def test_get_signals_is_long(self):
        self.ha_ewm._latest_data = {'D': pd.read_csv('test_data/ha_ewm_2_long_signal.csv')}
        self.ha_ewm._update_current_indicators_and_signals()
        self.assertEqual(self.ha_ewm._get_signals(), {'1': 'long'})

    def test_get_signals_is_short(self):
        self.ha_ewm._latest_data = {'D': pd.read_csv('test_data/ha_ewm_2_short_signal.csv')}
        self.ha_ewm._update_current_indicators_and_signals()
        self.assertEqual(self.ha_ewm._get_signals(), {'1': 'short'})

    def test_get_stop_loss_pip_amount(self):
        self.ha_ewm._latest_data = {'D': pd.read_csv('test_data/ha_ewm_2_long_signal.csv')}
        self.ha_ewm._strategy_atr_values = {}
        self.assertEqual(self.ha_ewm._get_stop_loss_pip_amount('long'), 1)

    def test_place_pending_order_correctly(self):
        self.ha_ewm._latest_data = {'D': pd.read_csv('test_data/ha_ewm_2_long_signal.csv')}
        self.ha_ewm._strategy_atr_values = {}
        self.ha_ewm._place_new_pending_order_if_units_available('1', 'long')


if __name__ == '__main__':
    unittest.main()
