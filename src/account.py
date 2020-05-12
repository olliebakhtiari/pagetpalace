# Local.
from src.request import RequestMixin
from config.settings import OANDA_DOMAINS


class Account(RequestMixin):
    PROTOCOL = 'https://'
    VERSION = 'v3'

    def __init__(self, access_token: str, account_id: str, account_type: str):
        self.url = f'{self.PROTOCOL}{self.domain}/{self.VERSION}/{account_id}/accounts'
        self.auth_token = access_token
        self.account_id = account_id
        self.account_type = account_type
        self.domain = OANDA_DOMAINS[self.account_type]  # LIVE-API or DEMO-API.

        # TODO: put urls into methods.
        self.order_urls = {
            'create_order': 'orders',
            'get_orders': 'orders',
            'get_pending_orders': 'pendingOrders',
            'get_order': 'orders/*orderSpecifier*',
            'replace_order': 'orders/*orderSpecifier*',
            'cancel_order': 'orders/*orderSpecifier/cancel',
        }
        self.default_headers = {
                'Authorization': f'Bearer {self.auth_token}',
                'X-Accept-Datetime-Format': 'unix',
            }
        self.default_params = {
                'accountId': self.account_id,
            }
        super().__init__(access_token, self.default_headers, self.default_params, self.url)

    def __str__(self):
        return f'{self.account_id} - {self.account_type}'

    # TODO: a lot needs to be rewritten to catch exceptions instead of allowing them to break execution and
    #       functionality needs to be added to individual method to extract necessary data.

    def get_current_orders_and_positions(self) -> dict:
        """ Get full details for an Account client has access to. Full pending orders, open trades and open positions.

        :return: JSON.
        """
        return self._request()

    def get_summary(self) -> dict:
        """ Get summary for a single account client has access to.

        :return: JSON.
        """
        return self._request(endpoint='summary')

    def get_tradeable_instruments(self) -> dict:
        """ Get list of tradeable instruments for the given account. The list of tradeable instruments in dependable
            on the regulatory divison the account is situated in.

        :return: JSON.
        """
        return self._request(endpoint='instruments')

    def get_state_and_changes(self) -> dict:
        """ Used to poll an account for its current state and changes since a specified transaction ID.

        :return: JSON.
        """
        return self._request(endpoint='changes')

    def get_trades(self) -> dict:
        """ Get a list of all trades for an account.

        :return: JSON.
        """
        return self._request(endpoint='trades')

    def get_open_trades(self) -> dict:
        """ Get the list of open trades for an account.

        :return: JSON.
        """
        return self._request(endpoint='openTrades')

    def close_trade(self, trade_specifier, close_amount="ALL") -> dict:
        """ Close (partially or fully) a specific open trade in an account.

        :param trade_specifier: Type - string, Format - Either the Trade’s OANDA-assigned TradeID or the Trade’s
                                client-provided ClientID prefixed by the “@” symbol, Example - @my_trade_id.
        :param close_amount:
        :return: JSON.
        """
        return self._request(
            endpoint=f'trades/{trade_specifier}/close',
            method='PUT',
            data={"units": close_amount},
        )

    def update_orders(self, trade_specifier, take_profit, stop_loss, trailing_stop_loss) -> dict:
        """ Create, replace or cancel a trade's dependent orders (Take Profit, Stop Loss and Trailing Stop Loss) through
            the trade itself.

        :param trade_specifier: Type - string, Format - Either the Trade’s OANDA-assigned TradeID or the Trade’s
                                client-provided ClientID prefixed by the “@” symbol, Example - @my_trade_id.
        :param take_profit: TakeProfitDetails is an application/json object with the following Schema:

                                {
                                    The price that the Take Profit Order will be triggered at. Only one of
                                    the price and distance fields may be specified.

                                    price : (PriceValue),


                                    The time in force for the created Take Profit Order. This may only be
                                    GTC, GTD or GFD.

                                    timeInForce : (TimeInForce, default=GTC),


                                    The date when the Take Profit Order will be cancelled on if timeInForce
                                    is GTD.

                                    gtdTime : (DateTime),


                                    The Client Extensions to add to the Take Profit Order when created.

                                    clientExtensions : (ClientExtensions)
                                }
        :param stop_loss: StopLossDetails is an application/json object with the following Schema:

                            {
                                The price that the Stop Loss Order will be triggered at. Only one of the
                                price and distance fields may be specified.

                                price : (PriceValue),


                                Specifies the distance (in price units) from the Trade’s open price to
                                use as the Stop Loss Order price. Only one of the distance and price
                                fields may be specified.

                                distance : (DecimalNumber),


                                The time in force for the created Stop Loss Order. This may only be GTC,
                                GTD or GFD.

                                timeInForce : (TimeInForce, default=GTC),


                                The date when the Stop Loss Order will be cancelled on if timeInForce is
                                GTD.

                                gtdTime : (DateTime),


                                The Client Extensions to add to the Stop Loss Order when created.

                                clientExtensions : (ClientExtensions),


                                Flag indicating that the price for the Stop Loss Order is guaranteed. The
                                default value depends on the GuaranteedStopLossOrderMode of the account,
                                if it is REQUIRED, the default will be true, for DISABLED or ENABLED the
                                default is false.


                                Deprecated: Will be removed in a future API update.

                                guaranteed : (boolean, deprecated)
                            }
        :param trailing_stop_loss: TrailingStopLossDetails is an application/json object with the following Schema:
                            {
                                The distance (in price units) from the Trade’s fill price that the
                                Trailing Stop Loss Order will be triggered at.

                                distance : (DecimalNumber),


                                The time in force for the created Trailing Stop Loss Order. This may only
                                be GTC, GTD or GFD.

                                timeInForce : (TimeInForce, default=GTC),


                                The date when the Trailing Stop Loss Order will be cancelled on if
                                timeInForce is GTD.

                                gtdTime : (DateTime),


                                The Client Extensions to add to the Trailing Stop Loss Order when
                                created.

                                clientExtensions : (ClientExtensions)
                            }
        :return: JSON.
        """
        return self._request(
            endpoint=f'trades/{trade_specifier}/orders',
            method='PUT',
            data={
                "takeProfit": take_profit,
                "stopLoss": stop_loss,
                "trailingStopLoss": trailing_stop_loss,
            },
        )

    def get_all_positions(self) -> dict:
        """ List all positions for an Account. The positions returned are for every instrument that has had a position
            during the lifetime of the account.

        :return: JSON.
        """
        return self._request(endpoint='positions')

    def get_open_positions(self) -> dict:
        """ List all open positions for an Account. An open position is a position in an account that currently has a
            trade opened for it.

        :return: JSON.
        """
        return self._request(endpoint='openPositions')

    def get_instrument_position(self, instrument: str) -> dict:
        """ Get the details of a single instruments position in an Account. The position may be open or not.

        :param instrument: e.g. GBP_USD.
        :return: JSON.
        """
        return self._request(endpoint=f'positions/{instrument}')

    def close_instrument_position(self, instrument: str) -> dict:
        """

        :param instrument:
        :return:
        """
        return self._request(endpoint=f'positions/{instrument}/close', method='PUT')

    def create_order(self):
        """ https://developer.oanda.com/rest-live-v20/order-df/#OrderRequest

        :return:
        """
        return

