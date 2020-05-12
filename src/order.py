class Order:
    """ Time in force:  GTC	- The Order is “Good unTil Cancelled”
                        GTD	- The Order is “Good unTil Date” and will be cancelled at the provided time
                        GFD	- The Order is “Good For Day” and will be cancelled at 5pm New York time
                        FOK	- The Order must be immediately “Filled Or Killed”
                        IOC	- The Order must be “Immediately partially filled Or Cancelled"

        Price:  The price threshold specified for the Limit Order. The Limit Order will only be filled by a market
                price that is equal to or better than this price.

        Price Bound: The worst price that the client is willing to have the Market Order filled at.

        Position Fill: OPEN_ONLY - When the Order is filled, only allow Positions to be opened or extended.
                       REDUCE_FIRST - When the Order is filled, always fully reduce an existing Position before opening
                                      a new Position.
                       REDUCE_ONLY - When the Order is filled, only reduce an existing Position.
                       DEFAULT - When the Order is filled, use REDUCE_FIRST behaviour for non-client hedging Accounts,
                                 and OPEN_ONLY behaviour for client hedging Accounts.

        Trigger Condition:  Specification of which price component should be used when determining if
                            an Order should be triggered and filled. This allows Orders to be
                            triggered based on the bid, ask, mid, default (ask for buy, bid for sell)
                            or inverse (ask for sell, bid for buy) price depending on the desired
                            behaviour. Orders are always filled using their default price component.
                            This feature is only provided through the REST API. Clients who choose to
                            specify a non-default trigger condition will not see it reflected in any
                            of OANDA’s proprietary or partner trading platforms, their transaction
                            history or their account statements. OANDA platforms always assume that
                            an Order’s trigger condition is set to the default value when indicating
                            the distance from an Order’s trigger price, and will always provide the
                            default trigger condition when creating or modifying an Order. A special
                            restriction applies when creating a guaranteed Stop Loss Order. In this
                            case the TriggerCondition value must either be “DEFAULT”, or the
                            “natural” trigger side “DEFAULT” results in. So for a Stop Loss Order for
                            a long trade valid values are “DEFAULT” and “BID”, and for short trades
                            “DEFAULT” and “ASK” are valid.
    """
    def __init__(
            self,
            instrument: str,
            order_type: str,
            units: float,
            time_in_force: str,
            price: str,
            position_fill: str,  # specification of how Positions in the Account are modified when the Order is filled.
            trigger_condition: str,
            stop_loss=None,
            take_profit=None,
            trailing_stop=None,
    ):
        self.instrument = instrument
        self.order_type = order_type
        self.units = units
        self.time_in_force = time_in_force
        self.price = price
        self.position_fill = position_fill
        self.trigger_condition = trigger_condition
        self._stop_loss = stop_loss
        self._take_profit = take_profit
        self._trailing_stop = trailing_stop

    def __str__(self):
        return f'{self.order_type} - {self.instrument} - {self.trigger_condition}'

    # TODO: check whether values entered are valid depending on long or short position. (check if units are pos or neg).

    @property
    def stop_loss(self):
        return self._stop_loss

    @stop_loss.setter
    def stop_loss(self, value):
        self._stop_loss = value

    @property
    def trailing_stop(self):
        return self._trailing_stop

    @trailing_stop.setter
    def trailing_stop(self, value):
        self._trailing_stop = value

    @property
    def take_profit(self):
        return self._take_profit

    @take_profit.setter
    def take_profit(self, value):
        self._take_profit = value

    def create_order(self):
        """ Return dict to be used as the parameters of the API request.

        :return:
        """
        return {
            "type": f"{self.order_type}",
            "instrument": f"{self.instrument}",
            "units": f"{self.units}",
            "price": f"{self.price}",
            "timeInForce": f"{self.time_in_force}",
            "positionFill": f"{self.position_fill}",
            "triggerCondition": f"{self.trigger_condition}",
            "takeProfitOnFill": f"{self._take_profit}",
            "stopLossOnFill": f"{self._stop_loss}",
            "trailingStopLossOnFill": f"{self._trailing_stop}"
        }
