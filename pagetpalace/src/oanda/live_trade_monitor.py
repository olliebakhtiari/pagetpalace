# Python standard.
from collections import defaultdict
from typing import Dict, List

# Local.
from pagetpalace.src.instruments import get_all_instruments
from pagetpalace.src.oanda.account import OandaAccount
from pagetpalace.src.oanda.pricing import OandaPricingData
from pagetpalace.src.oanda.calculations import calculate_new_sl_price, check_pct_hit
from pagetpalace.src.oanda.settings import LIVE_ACCESS_TOKEN, PRIMARY_ACCOUNT_NUMBER
from pagetpalace.src.trade_adjustment_params import PartialClosureParams, StopLossMoveParams, TradeAdjustmentParameters
from pagetpalace.tools.logger import *


class LiveTradeMonitor:
    ALL_INSTRUMENTS = get_all_instruments()

    def __init__(
            self,
            account: OandaAccount,
            stop_loss_move_params: List[StopLossMoveParams] = None,
            partial_closure_params: List[PartialClosureParams] = None,
    ):
        self._account = account
        self._pricing = OandaPricingData(LIVE_ACCESS_TOKEN, PRIMARY_ACCOUNT_NUMBER, 'LIVE_API')
        self.stop_loss_move_params = TradeAdjustmentParameters.init_pair_to_params(stop_loss_move_params)
        self.partial_closure_params = TradeAdjustmentParameters.init_pair_to_params(partial_closure_params)
        self.partially_closed = TradeAdjustmentParameters.init_local_history(partial_closure_params)
        self.sl_adjusted = TradeAdjustmentParameters.init_local_history(stop_loss_move_params)

    def _get_pair_to_open_trade_ids(self) -> Dict[str, List[str]]:
        pair_to_open_trade_ids = defaultdict(list)
        for trade in self._account.get_open_trades()['trades']:
            pair_to_open_trade_ids[trade['instrument']].append(trade['id'])

        return pair_to_open_trade_ids

    def _clean_local_lists(self, pair_to_open_trade_ids: Dict[str, List[str]]):
        for adjustment_attribute in [self.sl_adjusted, self.partially_closed]:
            for pair, local_lists in adjustment_attribute.items():
                for count, registered_ids in local_lists.items():
                    for id_ in registered_ids:
                        if id_ not in pair_to_open_trade_ids[pair]:
                            local_lists[count].remove(id_)

    def clean_lists(self):
        try:
            self._clean_local_lists(self._get_pair_to_open_trade_ids())
        except Exception as exc:
            logger.info(f'Failed to clean lists. {exc}', exc_info=True)

    def _get_prices_to_check(self, instrument_symbol: str) -> Dict[str, float]:
        tf_and_prices_id = f'{instrument_symbol}:S5:AB'
        latest_5s_prices = self._pricing.get_latest_candles(tf_and_prices_id)['latestCandles'][0]['candles'][-1]

        return {'ask_low': float(latest_5s_prices['ask']['l']), 'bid_high': float(latest_5s_prices['bid']['h'])}

    def _get_pair_to_prices(self, open_trades: List[dict]) -> Dict[str, Dict[str, float]]:
        pair_to_prices = {}
        for trade in open_trades:
            pair = trade['instrument']
            if not pair_to_prices.get(pair):
                pair_to_prices[pair] = self._get_prices_to_check(pair)

        return pair_to_prices

    def _check_and_adjust_stops(self, prices: Dict[str, float], trade: dict, params: Dict[int, Dict[str, float]]):
        symbol = trade['instrument']
        for count, percentages in params.items():
            if trade['id'] not in self.sl_adjusted[symbol][count]:
                has_pct_hit = check_pct_hit(prices, trade, percentages['check'])
                if has_pct_hit:
                    logger.info(f'Adjusting stop loss for: {trade}')
                    new_stop_loss_price = calculate_new_sl_price(trade=trade, pct=percentages['move'])
                    self._account.update_stop_loss(
                        trade_specifier=trade['id'],
                        price=round(new_stop_loss_price, self.ALL_INSTRUMENTS[symbol].price_precision),
                    )
                    self.sl_adjusted[symbol][count].append(trade['id'])
                else:

                    # No need to check subsequent targets if the previous hasn't been hit. "check" pct's are ascending.
                    return

    def _check_and_adjust_stop_losses(self, prices_to_check: Dict[str, Dict[str, float]], open_trades: List[dict]):
        if self.stop_loss_move_params:
            for trade in open_trades:
                symbol = trade['instrument']
                if symbol in self.sl_adjusted.keys():
                    try:
                        self._check_and_adjust_stops(
                            prices_to_check[symbol],
                            trade,
                            self.stop_loss_move_params[symbol],
                        )
                    except Exception as exc:
                        logger.error(f'Failed to check and adjust stop losses. {exc}', exc_info=True)

    def _check_and_partially_close(self, prices: Dict[str, float], trade: dict, params: Dict[int, Dict[str, float]]):
        symbol = trade['instrument']
        for count, percentages in params.items():
            if trade['id'] not in self.partially_closed[symbol][count]:
                is_pct_hit = check_pct_hit(prices, trade, percentages['check'])
                if is_pct_hit:
                    logger.info(f'Partially closing for: {trade}')
                    pct_of_units = round(abs(float(trade['currentUnits'])) * percentages['close'])
                    to_close = pct_of_units if pct_of_units > 1 else 1
                    self._account.close_trade(trade_specifier=trade['id'], close_amount=str(to_close))
                    self.partially_closed[symbol][count].append(trade['id'])
                else:

                    # No need to check subsequent targets if the previous hasn't been hit. "check" pct's are ascending.
                    return

    def _partial_closures(self, prices_to_check: Dict[str, Dict[str, float]], open_trades: List[dict]):
        if self.partial_closure_params:
            for trade in open_trades:
                symbol = trade['instrument']
                if symbol in self.partially_closed.keys():
                    try:
                        self._check_and_partially_close(
                            prices_to_check[symbol],
                            trade,
                            self.partial_closure_params[symbol],
                        )
                    except Exception as exc:
                        logger.error(f'Failed to check and partially close trades. {exc}', exc_info=True)

    def monitor_and_adjust_current_trades(self):
        try:
            open_trades = self._account.get_open_trades()['trades']
            if len(open_trades) > 0:
                pair_to_prices = self._get_pair_to_prices(open_trades)
                self._partial_closures(prices_to_check=pair_to_prices, open_trades=open_trades)
                self._check_and_adjust_stop_losses(prices_to_check=pair_to_prices, open_trades=open_trades)
        except Exception as exc:
            logger.error(f'Failed to monitor and adjust current trades. {exc}', exc_info=True)
