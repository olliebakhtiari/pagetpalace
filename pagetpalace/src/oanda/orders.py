# Python standard.
import json


class Orders:

    @classmethod
    def create_stop_order(cls,
                          entry: float,
                          price_bound: float,
                          sl: float,
                          tp: float,
                          instrument: str,
                          units: float):
        return json.dumps({
            "order": {
                "price": f"{entry}",
                "stopLossOnFill": {
                    "timeInForce": "GTC",
                    "price": f"{sl}"
                },
                "takeProfitOnFill": {
                    "timeInForce": "GTC",
                    "price": f"{tp}"
                },
                "timeInForce": "GTC",
                "instrument": instrument,
                "units": f"{units}",
                "type": "STOP",
                "positionFill": "DEFAULT",
                "priceBound": f"{price_bound}",
            }
        })
