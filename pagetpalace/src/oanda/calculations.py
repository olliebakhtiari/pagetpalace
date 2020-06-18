# Python standard.
from typing import Dict


def check_pct_hit(prices: Dict[str, float], trade: dict, pct: float) -> bool:
    has_hit = False
    if int(trade['currentUnits']) > 0:
        has_hit = _check_long_pct_hit(prices['bid_high'], trade, pct)
    elif int(trade['currentUnits']) < 0:
        has_hit = _check_short_pct_hit(prices['ask_low'], trade, pct)

    return has_hit


def _check_long_pct_hit(price: float, trade: dict, pct: float) -> bool:
    return price >= round((float(trade['price']) + _get_long_trade_pct_target_pips(trade, pct)), 1)


def _check_short_pct_hit(price: float, trade: dict, pct: float) -> bool:
    return price <= round((float(trade['price']) - _get_short_trade_pct_target_pips(trade, pct)), 1)


def calculate_new_sl_price(trade: dict, pct: float) -> float:
    price = trade['price']
    if int(trade['currentUnits']) > 0:
        price = _calculate_new_long_sl(trade, pct)
    elif int(trade['currentUnits']) < 0:
        price = _calculate_new_short_sl(trade, pct)

    return round(float(price), 1)


def _calculate_new_long_sl(trade: dict, pct: float) -> float:
    return float(trade['price']) + _get_long_trade_pct_target_pips(trade, pct)


def _calculate_new_short_sl(trade: dict, pct: float) -> float:
    return float(trade['price']) - _get_short_trade_pct_target_pips(trade, pct)


def _get_long_trade_pct_target_pips(trade: dict, pct: float) -> float:
    return (float(trade['takeProfitOrder']['price']) - float(trade['price'])) * pct


def _get_short_trade_pct_target_pips(trade: dict, pct: float) -> float:
    return (float(trade['price']) - float(trade['takeProfitOrder']['price'])) * pct
