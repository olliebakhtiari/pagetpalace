# Python standard.
import json


def create_market_if_touched_order(entry: float, sl: float, tp: float, instrument: str, units: float):
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
                "positionFill": "DEFAULT"
            }
        })

