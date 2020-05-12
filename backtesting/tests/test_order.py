# Python standard.
import unittest

# Local.
from backtesting.orders import OrderFactory, LongOrder, ShortOrder, LongDynamicSL, ShortDynamicSL


class TestLongOrder(unittest.TestCase):
    def setUp(self):
        self.long_order = LongOrder()

    def test_get_profit_status(self):
        pass

    def test_get_loss_status(self):
        pass

    def test_get_unchanged_status(self):
        pass

    def test_calculate_correct_profit(self):
        pass

    def test_calculate_correct_loss(self):
        pass


class TestShortOrder(unittest.TestCase):
    def setUp(self):
        self.short_order = ShortOrder()

    def test_get_profit_status(self):
        pass

    def test_get_loss_status(self):
        pass

    def test_get_unchanged_status(self):
        pass

    def test_calculate_correct_profit(self):
        pass

    def test_calculate_correct_loss(self):
        pass


class TestLongDynamicSL(unittest.TestCase):
    def setUp(self):
        self.long_dynamic_sl = LongDynamicSL()

    def test_get_profit_status(self):
        pass

    def test_get_loss_status(self):
        pass

    def test_get_unchanged_status(self):
        pass

    def test_calculate_take_profit_hit_correctly(self):
        pass

    def test_calculate_stop_loss_hit_correctly(self):
        pass


class TestShortDynamicSL(unittest.TestCase):
    def setUp(self):
        self.short_dynamic_sl = ShortDynamicSL()

    def test_get_profit_status(self):
        pass

    def test_get_loss_status(self):
        pass

    def test_get_unchanged_status(self):
        pass

    def test_calculate_take_profit_hit_correctly(self):
        pass

    def test_calculate_stop_loss_hit_correctly(self):
        pass


class TestOrderFactory(unittest.TestCase):
    def setUp(self):
        self.order_factor = OrderFactory()

    def test_return_correct_order_types(self):
        pass


if __name__ == '__main__':
    unittest.main()
