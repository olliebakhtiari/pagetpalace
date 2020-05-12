# Python standard.
import unittest
import datetime

# Local.
from backtesting.account import BackTestingAccount


class TestAccount(unittest.TestCase):
    def setUp(self) -> None:
        self.account = BackTestingAccount(starting_capital=10000, equity_split=6)

    def add_active_trade(self):
        self.account.open_trade(
            instrument_point_type='index',
            opened_at=datetime.datetime(year=2020, month=5, day=10, hour=12, minute=45, second=0),
            order_type='long_dynamic_sl',
            entry=2886.9,
            take_profit=2886.9 + 48.3,
            stop_loss=2886.9 - 16.1,
            margin_size=1500,
            label='3_long',
            spread=0.3,
        )
        self.account.process_pending_orders(
            long_prices_to_check=[2886.9],
            short_prices_to_check=[],
            valid_labels=['3_long'],
        )

    def test_get_tradeable_margin(self):
        self.assertEqual(self.account.get_tradeable_margin(), 9000)

    def test_calculate_pips_to_pounds(self):
        pounds = self.account.calculate_pips_to_pounds(1430, 100, 'index')
        self.assertEqual(pounds, 1000)

        pounds = self.account.calculate_pips_to_pounds(4260, 100, 'currency')
        self.assertEqual(pounds, 1000)

    def test_get_margin_size_per_trade(self):
        pips = 50
        risk = self.account.get_margin_size_per_trade(pips, 'index')
        self.assertEqual(risk, 1500.0)

        # pip amount exceeds max risk willing to take.
        pips = 150
        risk = self.account.get_margin_size_per_trade(pips, 'index')
        self.assertEqual(risk, 1430.0)

    def test_open_trade(self):
        self.account.open_trade(
            instrument_point_type='index',
            opened_at=datetime.datetime(year=2020, month=5, day=10, hour=12, minute=45, second=0),
            order_type='long_dynamic_sl',
            entry=2886.9,
            take_profit=2886.9+48.3,
            stop_loss=2886.9-16.1,
            margin_size=1500,
            label='3_long',
            spread=0.3,
        )
        pending_orders = self.account.get_pending_orders()
        self.assertEqual(len(pending_orders), 1)
        self.assertEqual(self.account.get_available_margin(), 10000 - 1500)

    def test_count_orders_by_label(self):
        self.account.open_trade(
            instrument_point_type='index',
            opened_at=datetime.datetime(year=2020, month=5, day=10, hour=12, minute=45, second=0),
            order_type='long_dynamic_sl',
            entry=2886.9,
            take_profit=2886.9 + 48.3,
            stop_loss=2886.9 - 16.1,
            margin_size=1500,
            label='3_long',
            spread=0.3,
        )
        self.account.open_trade(
            instrument_point_type='index',
            opened_at=datetime.datetime(year=2020, month=5, day=10, hour=12, minute=45, second=0),
            order_type='long_dynamic_sl',
            entry=2886.9,
            take_profit=2886.9+48.3,
            stop_loss=2886.9-16.1,
            margin_size=1500,
            label='3_short',
            spread=0.3,
        )
        self.account.open_trade(
            instrument_point_type='index',
            opened_at=datetime.datetime(year=2020, month=5, day=10, hour=12, minute=45, second=0),
            order_type='long_dynamic_sl',
            entry=2886.9,
            take_profit=2886.9+48.3,
            stop_loss=2886.9-16.1,
            margin_size=1500,
            label='2_long',
            spread=0.3,
        )
        self.assertEqual(self.account.count_orders_by_label('3'), 2)
        self.assertEqual(self.account.count_orders_by_label('2'), 1)
        self.assertEqual(self.account.count_orders_by_label('1'), 0)

    def test_move_pending_order_to_active_successfully(self):
        self.add_active_trade()
        self.assertEqual(len(self.account.get_pending_orders()), 0)
        self.assertEqual(self.account.has_active_trades(), True)

    def test_delete_invalid_pending_order(self):
        self.account.open_trade(
            instrument_point_type='index',
            opened_at=datetime.datetime(year=2020, month=5, day=10, hour=12, minute=45, second=0),
            order_type='long_dynamic_sl',
            entry=2886.9,
            take_profit=2886.9 + 48.3,
            stop_loss=2886.9 - 16.1,
            margin_size=1500,
            label='3_long',
            spread=0.3,
        )
        self.account.process_pending_orders(
            long_prices_to_check=[2886.9],
            short_prices_to_check=[],
            valid_labels=['3_short'],
        )
        self.assertEqual(len(self.account.get_pending_orders()), 0)
        self.assertEqual(self.account.has_active_trades(), False)
        self.assertEqual(self.account.get_available_margin(), 10000)

    def test_check_and_adjust_stop_losses(self):
        self.add_active_trade()
        trade = self.account._active_trades[0]

        # Move at 1:1
        self.account.check_and_adjust_stop_losses(
            check_pct=0.33,
            move_pct=0.01,
            long_price=2886.9 + 16.1,
            short_price=0,
        )
        self.assertEqual(trade.stop_loss, 2887.3830000000003)

        # Move at 2:1
        self.account.check_and_adjust_stop_losses(
            check_pct=0.66,
            move_pct=0.33,
            long_price=2886.9 + 32.2,
            short_price=0,
        )
        self.assertEqual(trade.stop_loss, 2902.839)

    def test_monitor_and_close_active_trades(self):
        self.add_active_trade()
        self.account.monitor_and_close_active_trades(
            current_date_time=datetime.datetime(year=2020, month=5, day=10, hour=12, minute=55, second=0),
            long_price=2886.9 + 48.3,
            short_price=0,
        )
        self.assertEqual(self.account.has_active_trades(), False)
        self.assertEqual(len(self.account._pending_orders), 0)
        self.assertEqual(len(self.account.get_closed_trades()), 1)
        self.assertEqual(self.account._pips_accumulated, 48.3)
        self.assertEqual(self.account._win_count, 1)
        self.assertEqual(self.account._loss_count, 0)
        self.assertEqual(self.account.get_available_margin(), 10000 + 503.496503496504)
        self.assertEqual(self.account.get_current_total_balance(), 10000 + 503.496503496504)

    def test_check_and_partially_close_trades(self):
        self.add_active_trade()
        self.account.check_and_partially_close_trades(
            0.5,
            long_price=2886.9 + 25,
            short_price=0,
            close_pct=0.25,
            partial_close_count=1,
        )
        partially_closed = self.account.get_partially_closed_trades()
        self.assertEqual(len(partially_closed[1]), 1)
        self.assertEqual(partially_closed[1][0].margin_size, 1500 - 375)

        # re-run first partial close, nothing should change.
        balance = self.account.get_current_total_balance()
        available_margin = self.account.get_available_margin()
        self.account.check_and_partially_close_trades(
            check_pct=0.5,
            long_price=2886.9 + 25,
            short_price=0,
            close_pct=0.25,
            partial_close_count=1,
        )
        self.assertEqual(self.account.get_current_total_balance(), balance)
        self.assertEqual(self.account.get_available_margin(), available_margin)

        # second partial close.
        self.account.check_and_partially_close_trades(
            check_pct=0.6,
            long_price=2886.9 + 35,
            short_price=0,
            close_pct=0.25,
            partial_close_count=2,
        )
        partially_closed = self.account.get_partially_closed_trades()
        self.assertEqual(len(partially_closed[2]), 1)
        self.assertEqual(partially_closed[2][0].margin_size, 843.75)


if __name__ == '__main__':
    unittest.main()
