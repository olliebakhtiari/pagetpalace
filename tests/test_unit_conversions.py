# Python standard.
import unittest

# Local.
from pagetpalace.src.instruments import CurrencyPairs, Indices, Commodities
from pagetpalace.src.oanda.unit_conversions import UnitConversions


class TestUnitConversions(unittest.TestCase):
    def setUp(self):
        self.eur_gbp = UnitConversions(CurrencyPairs.EUR_GBP, 0.88910)
        self.gbp_usd = UnitConversions(CurrencyPairs.GBP_USD, 1.35886)
        self.nas100_usd = UnitConversions(Indices.NAS100_USD, 12854.7)
        self.bco_usd = UnitConversions(Commodities.BCO_USD, 59.544)

    def test_get_pound_to_units_coefficient(self):
        self.assertEqual(self.eur_gbp._pound_to_units_variable, self.eur_gbp.entry_price)
        self.assertEqual(self.gbp_usd._pound_to_units_variable, 1.)
        self.assertLess(self.nas100_usd._pound_to_units_variable, 2)
        self.assertLess(self.bco_usd._pound_to_units_variable, 2)

    def test_calculate_units(self):
        margin = 10000
        self.assertEqual(self.eur_gbp.calculate_units(margin), 1)
        self.assertEqual(self.gbp_usd.calculate_units(margin), 1)
        self.assertEqual(self.nas100_usd.calculate_units(margin), 1)
        self.assertEqual(self.bco_usd.calculate_units(margin), 1)

    def test_calculate_pound_to_pip_ratio(self):
        self.assertEqual(self.eur_gbp.calculate_pound_to_pip_ratio(10000), 1)
        self.assertEqual(self.gbp_usd.calculate_pound_to_pip_ratio(10000), 1)
        self.assertEqual(self.nas100_usd.calculate_pound_to_pip_ratio(25), 1)
        self.assertEqual(self.bco_usd.calculate_pound_to_pip_ratio(250), 1)

    def test_convert_units_to_gbp(self):
        self.assertEqual(self.eur_gbp._convert_units_to_gbp(10000), 1)
        self.assertEqual(self.gbp_usd._convert_units_to_gbp(10000), 1)
        self.assertEqual(self.nas100_usd._convert_units_to_gbp(25), 1)
        self.assertEqual(self.bco_usd._convert_units_to_gbp(250), 1)


if __name__ == '__main__':
    unittest.main()
