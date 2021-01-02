# Python standard.
import unittest

# Local.
from pagetpalace.src.instruments import CurrencyPairs
from pagetpalace.src.risk_manager import RiskManager


class TestRiskManager(unittest.TestCase):
    def setUp(self):
        pair = CurrencyPairs.EUR_GBP
        pair.leverage = 10
        self.risk_manager = RiskManager(pair)
        self.trade_risk = self.risk_manager._calculate_risk(1328, 51.299, 2.)

    def test_calculate_risk(self):
        self.assertEqual(self.trade_risk, 2656.0)

    def test_is_more_than_max_risk(self):
        self.assertTrue(self.risk_manager._is_more_than_max_risk(self.trade_risk, 2500))
        self.assertFalse(self.risk_manager._is_more_than_max_risk(self.trade_risk, 15000))

    def test_adjust_risk(self):
        self.risk_manager.current_max_risk_in_margin = 1000
        self.assertEqual(self.risk_manager._adjust_risk(1328, self.trade_risk), 500.0)

    def test_calculate_margin_size_within_max_risk(self):
        self.assertEqual(self.risk_manager.calculate_unit_size_within_max_risk(5000, 1328, 51.299, 2.), 500)
        self.assertEqual(self.risk_manager.calculate_unit_size_within_max_risk(11000, 1328, 51.299, 5.), 440.)


if __name__ == '__main__':
    unittest.main()
