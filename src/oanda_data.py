# Python standard.
import datetime
from typing import List

# Third-party.
import pandas as pd

# Local.
from src.request import RequestMixin
from config.settings import OANDA_LIVE_ACCESS_TOKEN
from tools.datetime_utils import get_days_in_months, is_leap_year
from tools.data_operations import remove_duplicate_datetimes_from_csv
from tools.logger import *


class OandaInstrumentData(RequestMixin):
    PROTOCOL = 'https://'
    DOMAIN = 'api-fxtrade.oanda.com'
    VERSION = 'v3'

    DEFAULT_HEADERS = ['datetime', 'volume']
    PRICE_HEADERS = {
        'A': ['askOpen', 'askHigh', 'askLow', 'askClose'],
        'B': ['bidOpen', 'bidHigh', 'bidLow', 'bidClose'],
        'M': ['midOpen', 'midHigh', 'midLow', 'midClose'],
    }
    DATA_POINTS = ['o', 'h', 'l', 'c']

    def __init__(self, instrument: str):

        # A string containing the base currency and quote currency delimited by a “_”, e.g. GBP_USD.
        self.instrument = instrument
        self.url = f'{self.PROTOCOL}{self.DOMAIN}/{self.VERSION}/instruments/{self.instrument}'
        self.access_token = OANDA_LIVE_ACCESS_TOKEN
        self.default_headers = {
            'Authorization': f'Bearer {self.access_token}',
            'X-Accept-Datetime-Format': 'unix',
        }
        self.default_params = {}
        super().__init__(self.access_token, self.default_headers, self.default_params, self.url)

    def get_candlesticks(self,
                         prices: str = 'ABM',
                         granularity: str = 'D',
                         count: int = 14,
                         from_date: str = None,
                         to_date: str = None,
                         smooth: bool = False,
                         include_first: bool = True,
                         daily_alignment: int = 22,
                         alignment_timezone: str = 'Europe/London',
                         weekly_alignment: str = 'Sunday') -> dict:
        """ price: “M” (midpoint candles), “B” (bid candles) and “A” (ask candles).
            granularity: The granularity of the candlesticks to fetch [default=S5]
            count: The number of candlesticks to return in the response.
                   Count should not be specified if both the start and end parameters are
                   provided, as the time range combined with the granularity will determine
                   the number of candlesticks to return. [maximum=5000]
            from: The start of the time range to fetch candlesticks for. e.g. 2017-03-01T13:00:00.000000000Z
            to: The end of the time range to fetch candlesticks for. e.g. 2018-03-01T13:00:00.000000000Z
            smooth:	A flag that controls whether the candlestick is “smoothed” or not.
                    A smoothed candlestick uses the previous candle’s close price as its open price,
                    while an unsmoothed candlestick uses the first price from its
                    time range as its open price.
            includeFirst: A flag that controls whether the candlestick that is covered by
                         the from time should be included in the results.
                         This flag enables clients to use the timestamp of the last
                         completed candlestick received to poll for future candlesticks
                         but avoid receiving the previous candlestick repeatedly.
            dailyAlignment: The hour of the day (in the specified timezone) to use
                            for granularities that have daily alignments. [minimum=0, maximum=23]
            alignmentTimezone: The timezone to use for the dailyAlignment parameter.
                               Candlesticks with daily alignment will be aligned to the dailyAlignment
                               hour within the alignmentTimezone. Note that the returned times will
                               still be represented in UTC.
            weeklyAlignment: The day of the week used for granularities that have weekly alignment.
        """
        if prices not in 'ABM':
            raise ValueError('prices must be any combination of A, B and M')

        # include_first has no meaning without from_date being specified.
        if not from_date:
            include_first = None

        # can't specify count if both to and from are set.
        if to_date and from_date:
            count = None

        params = {
            "price": prices,
            "granularity": granularity,
            "count": count,
            "from": from_date,
            "to": to_date,
            "smooth": smooth,
            "includeFirst": include_first,
            "dailyAlignment": daily_alignment,
            "alignmentTimezone": alignment_timezone,
            "weeklyAlignment": weekly_alignment,
        }
        return self._request(endpoint='candles', params=params)

    @classmethod
    def convert_to_df(cls, candles: List[dict], prices: str) -> pd.DataFrame:
        """ candles expected to be list of dicts like: [
                                {
                                  "ask": {
                                    "c": "1.31469",
                                    "h": "1.31520",
                                    "l": "1.31467",
                                    "o": "1.31509"
                                  },
                                  "bid": {
                                    "c": "1.31454",
                                    "h": "1.31502",
                                    "l": "1.31450",
                                    "o": "1.31493"
                                  },
                                  "complete": true,
                                  "time": "2016-10-17T15:00:00.000000000Z",
                                  "volume": 70
                                }
                            ]
        """
        data = []
        headers = cls.DEFAULT_HEADERS
        for price_type in prices:
            headers.extend(cls.PRICE_HEADERS.get(price_type))
        for idx, candle in enumerate(candles):

            # format date string.
            date_, time_ = candle['time'].split('T')
            hr_mins_secs = time_.split('.')[0]
            date_time_str = f"{date_} {hr_mins_secs}"

            # append volume and datetime, returned df index stays as integers, change to datetime later if required.
            row = [date_time_str, candle['volume']]

            # add price data. maintain order, all ask first, then bid, then mid.
            if 'A' in prices:
                row.extend([candle['ask'][data_point] for data_point in cls.DATA_POINTS])
            if 'B' in prices:
                row.extend([candle['bid'][data_point] for data_point in cls.DATA_POINTS])
            if 'M' in prices:
                row.extend([candle['mid'][data_point] for data_point in cls.DATA_POINTS])
            data.append(row)

        return pd.DataFrame(data=data, columns=headers)

    @classmethod
    def calculate_end_date(cls, year: int, month: int, day: int):
        end_dt = datetime.datetime(year=year, month=month, day=day, hour=0, minute=0, second=0)
        td = datetime.timedelta(days=1)

        return str(end_dt + td).replace(' ', 'T')

    def write_candles_to_csv(self, granularity: str, output_loc: str, start_year: int, end_year: int, prices: str):
        days_in_month = get_days_in_months()
        now = datetime.datetime.now()
        candles = []
        for year in range(start_year, end_year+1):
            for month in range(1, 13):
                if not (year == now.year and month >= now.month - 1):
                    end_day = days_in_month[month]

                    # leap year for feb.
                    if is_leap_year(year) and month == 2:
                        end_day = 29

                    # Split in two halves as capped at 5000 candles per request.
                    resp_1 = self.get_candlesticks(
                        from_date=f'{year}-{month:02}-01T00:00:00.000000000Z',
                        to_date=f'{year}-{month:02}-15T00:00:00.000000000Z',
                        granularity=granularity,
                    )
                    resp_2 = self.get_candlesticks(
                        from_date=f'{year}-{month:02}-15T00:00:00.000000000Z',
                        to_date=f'{self.calculate_end_date(year, month, end_day)}.000000000Z',
                        granularity=granularity,
                    )
                    logger.info(resp_1)
                    logger.info(resp_2)
                    candles.extend(resp_1['candles'])
                    candles.extend(resp_2['candles'])
        logger.info(candles)
        df = self.convert_to_df(candles, prices)
        logger.info(df)
        df.to_csv(output_loc)
        remove_duplicate_datetimes_from_csv(output_loc)

    def get_order_book(self, time: str = None) -> dict:
        """ Fetch an order book for an instrument.

        :param time: The time of the snapshot to fetch. If not specified, then the most recent snapshot is fetched.
        """
        return self._request(endpoint='orderBook', params={"time": time} if time else {})

    def get_position_book(self, time: str = None) -> dict:
        """ Fetch a position book for an instrument.

        :param time: The time of the snapshot to fetch. If not specified, then the most recent snapshot is fetched.
        """
        return self._request(endpoint='positionBook', params={"time": time} if time else {})


if __name__ == '__main__':
    g = 'M5'
    od = OandaInstrumentData("GBP_USD")
    od.write_candles_to_csv(
        granularity=g,
        output_loc=f'/Users/oliver/Documents/pagetpalace/data/oanda/GBP_USD/GBPUSD_{g}.csv',
        start_year=2015,
        end_year=2020,
        prices='ABM',
    )


