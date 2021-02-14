# Python standard.
import unittest

# Third-party.
import pandas as pd

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
            boundary_multipliers={'D': {'long': {'below': 1}, 'short': {'above': 2}}},
            trade_multipliers={'1': {'long': {'tp': 3, 'sl': 1.5}, 'short': {'tp': 1.5, 'sl': 1.5}}},
            coefficients={
                'hp_coeffs': {'long': {'body': 3, 'shadow': 1.5}, 'short': {'body': 1.25, 'shadow': 2}},
                'streak_look_back': {'long': 1, 'short': 2},
                'price_movement_lb': {'long': 1, 'short': 2},
                'x_atr': {'long': 1, 'short': 1},
            },
        )

    def test_get_signals_is_long(self):
        self.hp_daily._latest_data = {'D': pd.read_csv('test_data/hp_daily_long_signal.csv')}
        self.hp_daily._strategy_atr_values = {'D': 0.01029}
        self.hp_daily._strategy_ssma_values = {'D': 1.24554}
        self.assertEqual(self.hp_daily._get_signals(), {'1': 'long'})

    def test_get_signals_is_short(self):
        self.hp_daily._latest_data = {'D': pd.read_csv('test_data/hp_daily_short_signal.csv')}
        self.hp_daily._strategy_atr_values = {'D': 0.01105}
        self.hp_daily._strategy_ssma_values = {'D': 1.29688}
        self.assertEqual(self.hp_daily._get_signals(), {'1': 'short'})

    def test_get_stop_loss_pip_amount(self):
        self.hp_daily._latest_data = {'D': pd.read_csv('test_data/hp_daily_long_signal.csv')}
        self.hp_daily._strategy_atr_values = {'D': 0.01000}
        self.assertEqual(self.hp_daily._get_stop_loss_pip_amount('long'), 0.029390000000000013)

    def test_place_market_order_correctly(self):
        self.hp_daily._latest_data = {'D': pd.read_csv('test_data/hp_daily_place_order.csv')}
        self.hp_daily._strategy_atr_values = {'D': 0.01000}
        self.hp_daily._place_market_order_if_units_available('1', 'long')


if __name__ == '__main__':
    unittest.main()
