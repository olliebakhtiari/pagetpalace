# Python standard.
import unittest

# Local.
from pagetpalace.src.instruments import CurrencyPairs, Indices, Commodities
from pagetpalace.src.oanda.unit_conversions import UnitConversions


class TestUnitConversions(unittest.TestCase):
    def setUp(self):
        self.gbp_usd = UnitConversions(instrument=CurrencyPairs.GBP_USD, entry_price=1.38439)
        self.eur_gbp = UnitConversions(instrument=CurrencyPairs.EUR_GBP, entry_price=0.87605)
        self.aud_jpy = UnitConversions(
            instrument=CurrencyPairs.AUD_JPY,
            entry_price=80.893,
            exchange_rates={'units': 1.79200, 'p2p': 145.022},
        )
        self.cad_chf = UnitConversions(
            instrument=CurrencyPairs.CAD_CHF,
            entry_price=0.70179,
            exchange_rates={'units': 1.75730, 'p2p': 1.23333},
        )
        self.bco_usd = UnitConversions(
            instrument=Commodities.BCO_USD,
            entry_price=61.625,
            exchange_rates={'p2p': 1.38420})
        self.gold_silver = UnitConversions(
            instrument=Commodities.GOLD_SILVER,
            entry_price=67.501,
            exchange_rates={'units': 1331.577, 'p2p': 19.72844},
        )
        self.de30_eur = UnitConversions(
            instrument=Indices.DE30_EUR,
            entry_price=14003.3,
            exchange_rates={'p2p': 0.87824},
        )
        self.nas100_usd = UnitConversions(
            instrument=Indices.NAS100_USD,
            entry_price=13743.6,
            exchange_rates={'p2p': 1.38420},
        )

    def test_calculate_units(self):
        self.assertEqual(self.gbp_usd.calculate_units(1150), 34500)
        self.assertEqual(self.eur_gbp.calculate_units(1150), 39381)
        self.assertEqual(self.aud_jpy.calculate_units(1150), 41216)
        self.assertEqual(self.cad_chf.calculate_units(1150), 50522)
        self.assertEqual(self.bco_usd.calculate_units(1150), 258)
        self.assertEqual(self.gold_silver.calculate_units(1150), 8)
        self.assertEqual(self.de30_eur.calculate_units(1500), 1)
        self.assertEqual(self.nas100_usd.calculate_units(145789), 293)

    def test_calculate_pip_to_pound_ratio(self):
        self.assertEqual(self.gbp_usd.calculate_pound_to_pip_ratio(self.gbp_usd.calculate_units(1150)), 2.49)
        self.assertEqual(self.eur_gbp.calculate_pound_to_pip_ratio(self.eur_gbp.calculate_units(1150)), 3.94)
        self.assertEqual(self.aud_jpy.calculate_pound_to_pip_ratio(self.aud_jpy.calculate_units(1150)), 2.84)
        self.assertEqual(self.cad_chf.calculate_pound_to_pip_ratio(self.cad_chf.calculate_units(1150)), 4.10)
        self.assertEqual(self.bco_usd.calculate_pound_to_pip_ratio(self.bco_usd.calculate_units(1150)), 1.86)
        self.assertEqual(self.gold_silver.calculate_pound_to_pip_ratio(self.gold_silver.calculate_units(1150)), 1.58)
        self.assertEqual(self.de30_eur.calculate_pound_to_pip_ratio(self.de30_eur.calculate_units(1150)), 0.88)
        self.assertEqual(self.nas100_usd.calculate_pound_to_pip_ratio(self.nas100_usd.calculate_units(145789)), 211.67)

    def test_convert_units_to_gbp(self):
        self.assertEqual(self.eur_gbp._convert_units_to_gbp(10000), 292.02)
        self.assertEqual(self.gbp_usd._convert_units_to_gbp(10000), 333.33)
        self.assertEqual(self.nas100_usd._convert_units_to_gbp(1), 496.45)
        self.assertEqual(self.bco_usd._convert_units_to_gbp(1), 4.45)
        self.assertEqual(self.cad_chf._convert_units_to_gbp(12000), 273.15)
        # self.assertEqual(self.de30_eur._convert_units_to_gbp(120), 73878)
        self.assertEqual(self.gold_silver._convert_units_to_gbp(250), 33289.43)


if __name__ == '__main__':
    unittest.main()
