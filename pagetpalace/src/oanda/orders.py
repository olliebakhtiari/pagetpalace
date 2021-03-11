# Python standard.
import json
from typing import Union


class Orders:

    @classmethod
    def create_stop_order(cls,
                          entry: float,
                          price_bound: Union[float, None],
                          stop_loss_price: float,
                          take_profit_price: float,
                          instrument: str,
                          units: int) -> str:
        order = {
            "order": {
                "price": f"{entry}",
                "stopLossOnFill": {
                    "timeInForce": "GTC",
                    "price": f"{stop_loss_price}"
                },
                "takeProfitOnFill": {
                    "timeInForce": "GTC",
                    "price": f"{take_profit_price}"
                },
                "timeInForce": "GTC",
                "instrument": instrument,
                "units": f"{units}",
                "type": "STOP",
                "positionFill": "DEFAULT",
            }
        }
        if price_bound:
            order["order"]["priceBound"] = f"{price_bound}"

        return json.dumps(order)

    @classmethod
    def create_market_order(cls,
                            stop_loss_price: float,
                            take_profit_price: float,
                            instrument: str,
                            units: int) -> str:
        return json.dumps({
            "order": {
                "stopLossOnFill": {
                    "timeInForce": "GTC",
                    "price": f"{stop_loss_price}"
                },
                "takeProfitOnFill": {
                    "timeInForce": "GTC",
                    "price": f"{take_profit_price}"
                },
                "timeInForce": "IOC",
                "instrument": instrument,
                "units": f"{units}",
                "type": "MARKET",
                "positionFill": "DEFAULT",
            }
        })
