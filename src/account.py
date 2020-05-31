# Python standard.
import json

# Local.
from src.request import RequestMixin
from settings import OANDA_DOMAINS


class Account(RequestMixin):
    PROTOCOL = 'https://'
    VERSION = 'v3'

    def __init__(self, access_token: str, account_id: str, account_type: str):
        self.account_type = account_type
        self.domain = OANDA_DOMAINS[self.account_type]  # LIVE-API or DEMO-API.
        self.auth_token = access_token
        self.account_id = account_id
        self.url = f'{self.PROTOCOL}{self.domain}/{self.VERSION}/accounts/{account_id}'
        self.default_headers = {
                'Authorization': f'Bearer {self.auth_token}',
                'X-Accept-Datetime-Format': 'unix',
                'Content-Type': 'application/json',
            }
        self.default_params = {
                'accountId': self.account_id,
            }
        super().__init__(access_token, self.default_headers, self.default_params, self.url)

    def __str__(self):
        return f'{self.account_id} - {self.account_type}'

    def get_full_account_details(self) -> dict:
        """ Get full details for an Account client has access to. Full pending orders, open trades and open positions.

        :return:
        """
        return self._request()

    def get_summary(self) -> dict:
        """ Get summary for a single account client has access to.

        :return:
        """
        return self._request(endpoint='summary')

    def get_tradeable_instruments(self) -> dict:
        """ Get list of trade-able instruments for the given account. The list of tradeable instruments in dependable
            on the regulatory division the account is situated in.

        :return:
        """
        return self._request(endpoint='instruments')

    def get_state_and_changes(self) -> dict:
        """ Used to poll an account for its current state and changes since a specified transaction ID.

        :return:
        """
        return self._request(endpoint='changes')

    def get_trades(self) -> dict:
        """ Get a list of all trades for an account.

        :return:
        """
        return self._request(endpoint='trades')

    def get_open_trades(self) -> dict:
        """ Get the list of open trades for an account.

        :return:
        """
        return self._request(endpoint='openTrades')

    def close_trade(self, trade_specifier: str, close_amount: str = "ALL") -> dict:
        """ Close (partially or fully) a specific open trade in an account.

        :return:
        """
        return self._request(
            endpoint=f'trades/{trade_specifier}/close',
            method='PUT',
            data=json.dumps({"units": close_amount}),
        )

    def update_stop_loss(self, trade_specifier: str, price: float):
        """ Create, replace or cancel a trade's dependent orders. Stop loss only.

        :return:
        """
        return self._request(
            endpoint=f'trades/{trade_specifier}/orders',
            method='PUT',
            data=json.dumps({"stopLoss": {"timeInForce": "GTC", "price": f"{price}"}}),
        )

    def update_take_profit(self, trade_specifier: str, price: float):
        """ Create, replace or cancel a trade's dependent orders. Take profit only.

        :return:
        """
        return self._request(
            endpoint=f'trades/{trade_specifier}/orders',
            method='PUT',
            data=json.dumps({"takeProfit": {"timeInForce": "GTC", "price": f"{price}"}}),
        )

    def update_dependent_orders(self, trade_specifier: str, take_profit_price: float, stop_loss_price: float) -> dict:
        """ Create, replace or cancel a trade's dependent orders (Take Profit, Stop Loss and Trailing Stop Loss) through
            the trade itself.

        :return:
        """
        return self._request(
            endpoint=f'trades/{trade_specifier}/orders',
            method='PUT',
            data=json.dumps({
                "takeProfit": {"timeInForce": "GTC", "price": f"{take_profit_price}"},
                "stopLoss": {"timeInForce": "GTC", "price": f"{stop_loss_price}"},
            }),
        )

    def get_all_positions(self) -> dict:
        """ List all positions for an Account. The positions returned are for every instrument that has had a position
            during the lifetime of the account.

        :return:
        """
        return self._request(endpoint='positions')

    def get_open_positions(self) -> dict:
        """ List all open positions for an Account. An open position is a position in an account that currently has a
            trade opened for it.

        :return:
        """
        return self._request(endpoint='openPositions')

    def get_instrument_position(self, instrument: str) -> dict:
        """ Get the details of a single instruments position in an Account. The position may be open or not.

        :param instrument: e.g. GBP_USD.
        :return:
        """
        return self._request(endpoint=f'positions/{instrument}')

    def close_instrument_position(self, instrument: str) -> dict:
        """ Closeout the open Position for a specific instrument in an Account.

        :return:
        """
        return self._request(endpoint=f'positions/{instrument}/close', method='PUT')

    def create_order(self, order: dict) -> dict:
        """ https://developer.oanda.com/rest-live-v20/order-df/#OrderRequest

        :return:
        """
        return self._request(endpoint='orders', method='POST', data=order)

    def get_orders(self) -> dict:
        """ Get a list of orders for an Account.

        :return:
        """
        return self._request(endpoint='orders', method='GET')

    def get_pending_orders(self) -> dict:
        """ List all pending Orders in an Account.

        :return:
        """
        return self._request(endpoint='pendingOrders', method='GET')

    def get_order(self, order_specifier: str) -> dict:
        """ Get details for a single Order in an Account.

        :return:
        """
        return self._request(endpoint=f'orders/{order_specifier}', method='GET')

    def replace_order(self, order_specifier: str) -> dict:
        """ Replace an Order in an Account by simultaneously cancelling it and creating a replacement Order.

        :return:
        """
        return self._request(endpoint=f'orders/{order_specifier}', method='PUT')

    def cancel_order(self, order_specifier: str) -> dict:
        """ Cancel a pending Order in an Account.

        :return:
        """
        return self._request(endpoint=f'orders/{order_specifier}/cancel', method='PUT')
