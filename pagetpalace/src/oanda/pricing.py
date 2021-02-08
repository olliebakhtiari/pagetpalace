# Python standard.
import datetime
from typing import List

# Local.
from pagetpalace.src.oanda.account import OandaAccount


class OandaPricingData(OandaAccount):
    def __init__(self, access_token: str, account_id: str, account_type: str):
        super().__init__(access_token, account_id, account_type)

    def get_latest_candles(self,
                           candle_specifications: str,
                           units: int = 1,
                           smooth: bool = False,
                           daily_alignment: int = 22,
                           alignment_timezone: str = 'Europe/London',
                           weekly_alignment: str = 'Sunday') -> dict:
        """ Get dancing bears and most recently completed candles within an Account for specified combinations of
            instrument, granularity and price component.

            candle_specifications: A string containing the following, all delimited by “:” characters:
                                   1) InstrumentName
                                   2) CandlestickGranularity
                                   3) PricingComponent e.g. EUR_USD:S10:BM
        """
        params = {
            "candleSpecifications": candle_specifications,
            "units": units,
            "smooth": smooth,
            "dailyAlignment": daily_alignment,
            "alignmentTimezone": alignment_timezone,
            "weeklyAlignment": weekly_alignment,
        }

        return self._request(endpoint='candles/latest', params=params)

    def get_pricing_info(self, instruments: List[str], since: str = '', include_home_conversions: bool = False) -> dict:
        """ Get pricing information for a specified list of instruments within an Account.
            since: “YYYY-MM-DDTHH:MM:SS.nnnnnnnnnZ”
        """
        if not since:
            td = datetime.timedelta(hours=2)
            dt = datetime.datetime.now() - td
            since = f'{dt.year}-{dt.month:02}-{dt.day:02}T{dt.hour:02}:{dt.minute:02}:{dt.second:02}.000000000Z'
        params = {
            "instruments": f"{','.join(instruments)}",
            "since": since,
            "includeHomeConversions": include_home_conversions,
        }

        return self._request(endpoint='pricing', params=params)

