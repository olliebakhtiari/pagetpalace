# Python standard.
import unittest

# Local.
from src.oanda_account import OandaAccount
from live_implementations.ssl_multi_time_frame import SSLMultiTimeFrame
from settings import DEMO_ACCESS_TOKEN, DEMO_V20_ACCOUNT_NUMBER


class TestSSLMulti(unittest.TestCase):
    """
    EXAMPLE ACCOUNT DETAILS OBJECT:
            {
                'guaranteedStopLossOrderMode': 'DISABLED',
                'hedgingEnabled': False,
                'id': '101-004-14597634-001',
                'createdTime': '2020-05-03T09:53:33.036756359Z',
                'currency': 'GBP',
                'createdByUserID': 14597634,
                'alias': 'Primary',
                'marginRate': '0.02',
                'lastTransactionID': '32',
                'balance': '99999.4176',
                'openTradeCount': 1,
                'openPositionCount': 1,
                'pendingOrderCount': 2,
                'pl': '0.0000',
                'resettablePL': '0.0000',
                'resettablePLTime': '0',
                'financing': '-0.7718',
                'commission': '0.0000',
                'dividendAdjustment': '0.1894',
                'guaranteedExecutionFees': '0.0000',
                'lastDividendAdjustmentTimestamps': [
                    {
                        'instrument': 'SPX500_USD',
                        'timestamp': '2020-06-01T22:00:07.702704180Z'
                    }
                ],
                'orders': [
                    {
                        'id': '6',
                        'createTime': '2020-05-29T20:40:51.685944939Z',
                        'type': 'TAKE_PROFIT',
                        'tradeID': '5',
                        'price': '3161.0',
                        'timeInForce': 'GTC',
                        'triggerCondition': 'DEFAULT',
                        'state': 'PENDING'
                    },
                    {
                        'id': '22',
                        'createTime': '2020-06-01T09:23:45.768457461Z',
                        'replacesOrderID': '7',
                        'type': 'STOP_LOSS',
                        'tradeID': '5',
                        'price': '3000.1',
                        'timeInForce': 'GTC',
                        'triggerCondition': 'DEFAULT',
                        'state': 'PENDING'
                    }
                ],
                'positions': [
                    {
                        'instrument': 'SPX500_USD',
                        'long': {
                            'units': '1',
                            'averagePrice': '3061.0',
                            'pl': '0.0000',
                            'resettablePL': '0.0000',
                            'financing': '-0.7718',
                            'dividendAdjustment': '0.1894',
                            'guaranteedExecutionFees': '0.0000',
                            'tradeIDs': ['5'],
                            'unrealizedPL': '5.9497'
                        },
                        'short': {
                            'units': '0',
                            'pl': '0.0000',
                            'resettablePL': '0.0000',
                            'financing': '0.0000',
                            'dividendAdjustment': '0.0000',
                            'guaranteedExecutionFees': '0.0000',
                            'unrealizedPL': '0.0000'
                        },
                        'pl': '0.0000',
                        'resettablePL': '0.0000',
                        'financing': '-0.7718',
                        'commission': '0.0000',
                        'dividendAdjustment': '0.1894',
                        'guaranteedExecutionFees': '0.0000',
                        'unrealizedPL': '5.9497',
                        'marginUsed': '122.3300'
                    }
                ],
                'trades': [
                    {
                        'id': '5',
                        'instrument': 'SPX500_USD',
                        'price': '3061.0',
                        'openTime': '2020-05-29T20:40:51.685944939Z',
                        'initialUnits': '1',
                        'initialMarginRequired': '123.8700',
                        'state': 'OPEN',
                        'currentUnits': '1',
                        'realizedPL': '0.0000',
                        'financing': '-0.7718',
                        'dividendAdjustment': '0.1894',
                        'takeProfitOrderID': '6',
                        'stopLossOrderID': '22',
                        'unrealizedPL': '5.9497',
                        'marginUsed': '122.3300'
                        }
                ],
                'unrealizedPL': '5.9497',
                'NAV': '100005.3673',
                'marginUsed': '122.3300',
                'marginAvailable': '99883.0669',
                'positionValue': '2446.6000',
                'marginCloseoutUnrealizedPL': '6.0594',
                'marginCloseoutNAV': '100005.4770',
                'marginCloseoutMarginUsed': '122.3300',
                'marginCloseoutPositionValue': '2446.6000',
                'marginCloseoutPercent': '0.00061',
                'withdrawalLimit': '99883.0669',
                'marginCallMarginUsed': '122.3300',
                'marginCallPercent': '0.00122'
            }

    EXAMPLE TRADE OBJECT:
            [{
                    'id': '5',
                    'instrument': 'SPX500_USD',
                    'price': '3061.0',
                    'openTime': '2020-05-29T20:40:51.685944939Z',
                    'initialUnits': '1',
                    'initialMarginRequired': '123.8700',
                    'state': 'OPEN',
                    'currentUnits': '1',
                    'realizedPL': '0.0000',
                    'financing': '-0.5813',
                    'dividendAdjustment': '0.0000',
                    'unrealizedPL': '-0.7324',
                    'marginUsed': '123.8950',
                    'takeProfitOrder': {
                        'id': '6',
                        'createTime': '2020-05-29T20:40:51.685944939Z',
                        'type': 'TAKE_PROFIT',
                        'tradeID': '5',
                        'price': '3161.0',
                        'timeInForce': 'GTC',
                        'triggerCondition': 'DEFAULT',
                        'state': 'PENDING'
                    },
                    'stopLossOrder': {
                        'id': '7',
                        'createTime': '2020-05-29T20:40:51.685944939Z',
                        'type': 'STOP_LOSS',
                        'tradeID': '5',
                        'price': '2961.0',
                        'timeInForce': 'GTC',
                        'triggerCondition': 'DEFAULT',
                        'state': 'PENDING'
                    }
                }]
            """
    def setUp(self):
        self.s = SSLMultiTimeFrame(
            OandaAccount(account_id=DEMO_V20_ACCOUNT_NUMBER, access_token=DEMO_ACCESS_TOKEN, account_type='DEMO_API')
        )
        self.trades = [
            {
                'id': '5',
                'instrument': 'SPX500_USD',
                'price': '3000.0',
                'openTime': '2020-05-29T20:40:51.685944939Z',
                'initialUnits': '1',
                'initialMarginRequired': '123.8700',
                'state': 'OPEN',
                'currentUnits': '1',
                'realizedPL': '0.0000',
                'financing': '-0.5813',
                'dividendAdjustment': '0.0000',
                'unrealizedPL': '-0.7324',
                'marginUsed': '123.8950',
                'takeProfitOrder': {
                    'id': '6',
                    'createTime': '2020-05-29T20:40:51.685944939Z',
                    'type': 'TAKE_PROFIT',
                    'tradeID': '5',
                    'price': '3500.0',
                    'timeInForce': 'GTC',
                    'triggerCondition': 'DEFAULT',
                    'state': 'PENDING'
                },
                'stopLossOrder': {
                    'id': '7',
                    'createTime': '2020-05-29T20:40:51.685944939Z',
                    'type': 'STOP_LOSS',
                    'tradeID': '5',
                    'price': '2500.0',
                    'timeInForce': 'GTC',
                    'triggerCondition': 'DEFAULT',
                    'state': 'PENDING'
                }
            },
            {
                'id': '5',
                'instrument': 'SPX500_USD',
                'price': '3000.0',
                'openTime': '2020-05-29T20:40:51.685944939Z',
                'initialUnits': '-1',
                'initialMarginRequired': '123.8700',
                'state': 'OPEN',
                'currentUnits': '-1',
                'realizedPL': '0.0000',
                'financing': '-0.5813',
                'dividendAdjustment': '0.0000',
                'unrealizedPL': '-0.7324',
                'marginUsed': '123.8950',
                'takeProfitOrder': {
                    'id': '6',
                    'createTime': '2020-05-29T20:40:51.685944939Z',
                    'type': 'TAKE_PROFIT',
                    'tradeID': '5',
                    'price': '2500.0',
                    'timeInForce': 'GTC',
                    'triggerCondition': 'DEFAULT',
                    'state': 'PENDING'
                },
                'stopLossOrder': {
                    'id': '7',
                    'createTime': '2020-05-29T20:40:51.685944939Z',
                    'type': 'STOP_LOSS',
                    'tradeID': '5',
                    'price': '3500.0',
                    'timeInForce': 'GTC',
                    'triggerCondition': 'DEFAULT',
                    'state': 'PENDING'
                }
            },
            {
                'id': '5',
                'instrument': 'SPX500_USD',
                'price': '3000.0',
                'openTime': '2020-05-29T20:40:51.685944939Z',
                'initialUnits': '-1',
                'initialMarginRequired': '123.8700',
                'state': 'OPEN',
                'currentUnits': '-1',
                'realizedPL': '0.0000',
                'financing': '-0.5813',
                'dividendAdjustment': '0.0000',
                'unrealizedPL': '-0.7324',
                'marginUsed': '123.8950',
                'takeProfitOrder': {
                    'id': '6',
                    'createTime': '2020-05-29T20:40:51.685944939Z',
                    'type': 'TAKE_PROFIT',
                    'tradeID': '5',
                    'price': '2350.0',
                    'timeInForce': 'GTC',
                    'triggerCondition': 'DEFAULT',
                    'state': 'PENDING'
                },
                'stopLossOrder': {
                    'id': '7',
                    'createTime': '2020-05-29T20:40:51.685944939Z',
                    'type': 'STOP_LOSS',
                    'tradeID': '5',
                    'price': '3500.0',
                    'timeInForce': 'GTC',
                    'triggerCondition': 'DEFAULT',
                    'state': 'PENDING'
                }
            }
        ]

    def test_check_pct_hit(self):
        prices = {'ask_low': 2625., 'bid_high': 3175.}
        self.assertEqual(self.s._check_pct_hit(prices=prices, trade=self.trades[0], pct=0.35), True)
        self.assertEqual(self.s._check_pct_hit(prices=prices, trade=self.trades[1], pct=0.75), True)
        self.assertEqual(self.s._check_pct_hit(prices=prices, trade=self.trades[-1], pct=0.75), False)

    def test_calculate_new_sl_price(self):
        self.assertEqual(self.s._calculate_new_sl_price(self.trades[0], 0.01), 3005)
        self.assertEqual(self.s._calculate_new_sl_price(self.trades[0], 0.35), 3175)
        self.assertEqual(self.s._calculate_new_sl_price(self.trades[-1], 0.01), 2993.5)
        self.assertEqual(self.s._calculate_new_sl_price(self.trades[-1], 0.35), 3000 - 227.49999999999997)

    def test_get_unit_size_per_trade(self):
        no_orders_or_trades = {
            'balance': '100000.00',
            'marginAvailable': '100000.00',
            'openTradeCount': 0,
            'openPositionCount': 0,
            'pendingOrderCount': 0,
            'orders': [],
            'positions': [],
            'trades': [],
        }
        with_pending_orders = {  # 85470
            'balance': '100000.00',
            'marginAvailable': '100000.00',
            'openTradeCount': 0,
            'openPositionCount': 0,
            'pendingOrderCount': 4,
            'orders': [
                {
                    'id': '6',
                    'createTime': '2020-05-29T20:40:51.685944939Z',
                    'type': 'TAKE_PROFIT',
                    'tradeID': '5', 'price': '3161.0', 'timeInForce': 'GTC', 'triggerCondition': 'DEFAULT',
                    'state': 'PENDING'
                },
                {
                    'id': '22', 'createTime': '2020-06-01T09:23:45.768457461Z', 'replacesOrderID': '7',
                    'type': 'STOP_LOSS', 'tradeID': '5', 'price': '3000.1', 'timeInForce': 'GTC',
                    'triggerCondition': 'DEFAULT', 'state': 'PENDING'
                },
                {
                    'id': '33', 'createTime': '2020-06-02T19:17:31.754242653Z', 'type': 'MARKET_IF_TOUCHED',
                    'instrument': 'SPX500_USD', 'units': '350', 'timeInForce': 'GTC',
                    'takeProfitOnFill': {'price': '3220.0', 'timeInForce': 'GTC'},
                    'stopLossOnFill': {'price': '3020.0', 'timeInForce': 'GTC'},
                    'price': '3120.0', 'triggerCondition': 'DEFAULT', 'partialFill': 'DEFAULT_FILL',
                    'positionFill': 'DEFAULT', 'state': 'PENDING'
                },
                {
                    'id': '34', 'createTime': '2020-06-02T19:17:53.671047563Z', 'type': 'MARKET_IF_TOUCHED',
                    'instrument': 'SPX500_USD', 'units': '-350', 'timeInForce': 'GTC',
                    'takeProfitOnFill': {'price': '2880.0', 'timeInForce': 'GTC'},
                    'stopLossOnFill': {'price': '3080.0', 'timeInForce': 'GTC'},
                    'price': '2980.0', 'triggerCondition': 'DEFAULT', 'partialFill': 'DEFAULT_FILL',
                    'positionFill': 'DEFAULT', 'state': 'PENDING'
                }
            ],
            'positions': [],
            'trades': [],
        }
        self.assertEqual(self.s.get_unit_size_per_trade(no_orders_or_trades), 420)
        self.assertEqual(self.s.get_unit_size_per_trade(with_pending_orders), 36)


if __name__ == '__main__':
    unittest.main()
