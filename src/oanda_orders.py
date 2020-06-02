# Python standard.
import json


def create_market_if_touched_order(entry: float,
                                   price_bound: float,
                                   sl: float,
                                   tp: float,
                                   instrument: str,
                                   units: float) -> dict:
    return json.dumps({
            "order": {
                "price": f"{entry}",
                "stopLossOnFill": {
                    "timeInForce": "GTC",
                    "price": f"{sl}"
                },
                "takeProfitOnFill": {
                    "price": f"{tp}"
                },
                "timeInForce": "GTC",
                "instrument": instrument,
                "units": f"{units}",
                "type": "MARKET_IF_TOUCHED",
                "positionFill": "DEFAULT",
                "priceBound": f"{price_bound}"
            }
        })

