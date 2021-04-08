# Python standard.
import datetime
import math
from typing import List

# Third-party.
import pandas as pd

# Local.
from pagetpalace.src.request import RequestMixin
from pagetpalace.src.oanda.settings import LIVE_ACCESS_TOKEN, OANDA_DOMAINS, OANDA_API_VERSION, PROTOCOL
from pagetpalace.tools.file_operations import remove_duplicate_datetimes_from_csv
from pagetpalace.tools.logger import *


class OandaInstrumentData(RequestMixin):
    DEFAULT_HEADERS = ['datetime', 'volume']
    PRICE_HEADERS = {
        'A': ['askOpen', 'askHigh', 'askLow', 'askClose'],
        'B': ['bidOpen', 'bidHigh', 'bidLow', 'bidClose'],
        'M': ['midOpen', 'midHigh', 'midLow', 'midClose'],
    }
    DATA_POINTS = ['o', 'h', 'l', 'c']

    def __init__(self):
        self.url = f'{PROTOCOL}{OANDA_DOMAINS["LIVE_API"]}/{OANDA_API_VERSION}/instruments/'
        self.access_token = LIVE_ACCESS_TOKEN
        self.default_headers = {
            'Authorization': f'Bearer {self.access_token}',
            'X-Accept-Datetime-Format': 'unix',
        }
        self.default_params = {}
        super().__init__(self.access_token, self.default_headers, self.default_params, self.url)

    def get_complete_candlesticks(self,
                                  instrument: str,
                                  prices: str = 'ABM',
                                  granularity: str = 'D',
                                  count: int = 14,
                                  from_date: str = None,
                                  to_date: str = None,
                                  smooth: bool = False,
                                  include_first: bool = True,
                                  daily_alignment: int = 22,
                                  alignment_timezone: str = 'Europe/London',
                                  weekly_alignment: str = 'Friday') -> List[dict]:
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
        response = self._request(endpoint=f'{instrument}/candles', params=params)

        return [candle for candle in response['candles'] if candle['complete']]

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
        headers = cls.DEFAULT_HEADERS.copy()
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
    def get_days_in_months(cls) -> dict:
        return {
            1: 31,
            2: 28,  # account for leap year when using.
            3: 31,
            4: 30,
            5: 31,
            6: 30,
            7: 31,
            8: 31,
            9: 30,
            10: 31,
            11: 30,
            12: 31,
        }

    @classmethod
    def is_leap_year(cls, year: int) -> bool:
        return year % 4 == 0 and (year % 100 != 0 or year % 400 == 0)

    @classmethod
    def calculate_end_date(cls, year: int, month: int, day: int) -> str:
        end_dt = datetime.datetime(year=year, month=month, day=day, hour=0, minute=0, second=0)
        td = datetime.timedelta(days=1)

        return str(end_dt + td).replace(' ', 'T')

    def get_from_and_to_dates_above_minute_granularity(self, year: int, month: int, end_day: int) -> List[dict]:
        return [
            {
                'from': f'{year}-{month:02}-01T00:00:00.000000000Z',
                'to': f'{year}-{month:02}-15T00:00:00.000000000Z',
            },
            {
                'from': f'{year}-{month:02}-15T00:00:00.000000000Z',
                'to': f'{self.calculate_end_date(year, month, end_day)}.000000000Z',
            },
        ]

    def get_from_and_to_dates_minute_data(self, year: int, month: int, end_day: int) -> List[dict]:
        end_date = self.calculate_end_date(year, month, end_day)
        dates = []
        for day in range(1, end_day):
            dates.append({
                'from': f'{year}-{month:02}-{day:02}T00:00:00.000000000Z',
                'to': f'{year}-{month:02}-{day+1:02}T00:00:00.000000000Z',
            })
        dates.append({
            'from': f'{year}-{month:02}-{end_day-1}T00:00:00.000000000Z',
            'to': f'{end_date}.000000000Z',
        })

        return dates

    def get_from_and_to_dates(self, granularity: str, year: int, month: int, end_day: int) -> List[dict]:
        if granularity == 'M1':
            dates = self.get_from_and_to_dates_minute_data(year, month, end_day)
        else:
            dates = self.get_from_and_to_dates_above_minute_granularity(year, month, end_day)

        return dates

    def write_candles_to_csv(
            self,
            instrument: str,
            granularity: str,
            output_loc: str,
            start_year: int,
            end_year: int,
            prices: str,
    ):
        days_in_month = self.get_days_in_months()
        now = datetime.datetime.now()
        candles = []
        for year in range(start_year, end_year + 1):
            for month in range(1, 13):
                if not (year == now.year and month >= now.month):
                    end_day = days_in_month[month]

                    # leap year for feb.
                    if self.is_leap_year(year) and month == 2:
                        end_day = 29

                    # Split into parts as capped at 5000 candles per request.
                    from_and_to_dates = self.get_from_and_to_dates(granularity, year, month, end_day)
                    for dates in from_and_to_dates:
                        response = self.get_complete_candlesticks(
                            instrument=instrument,
                            from_date=dates['from'],
                            to_date=dates['to'],
                            granularity=granularity,
                        )
                        logger.info(response)
                        candles.extend(response)
        if granularity != 'M1':
            curr_month_halfway = math.ceil(now.day) / 2
            curr_month_from_and_to = [
                {
                    'from': f'{now.year}-{now.month:02}-01T00:00:00.000000000Z',
                    'to': f'{now.year}-{now.month:02}-{curr_month_halfway:02}T00:00:00.000000000Z',
                },
                {
                    'from': f'{now.year}-{now.month:02}-{curr_month_halfway:02}T00:00:00.000000000Z',
                    'to': f'{now.year}-{now.month:02}-{now.day:02}T00:00:00.000000000Z',
                },
            ]
            for dates in curr_month_from_and_to:
                response = self.get_complete_candlesticks(
                    instrument=instrument,
                    from_date=dates['from'],
                    to_date=dates['to'],
                    granularity=granularity,
                )
                logger.info(response)
                candles.extend(response)
        logger.info(candles)
        df = self.convert_to_df(candles, prices)
        logger.info(df)
        df.to_csv(output_loc)
        remove_duplicate_datetimes_from_csv(output_loc)

    def get_order_book(self, instrument: str, time: str = None) -> dict:
        """ Fetch an order book for an instrument.

        :param instrument:
        :param time: The time of the snapshot to fetch. If not specified, then the most recent snapshot is fetched.
        """
        return self._request(endpoint=f'{instrument}/orderBook', params={"time": time} if time else {})

    def get_position_book(self, instrument: str, time: str = None) -> dict:
        """ Fetch a position book for an instrument.

        :param instrument:
        :param time: The time of the snapshot to fetch. If not specified, then the most recent snapshot is fetched.
        """
        return self._request(endpoint=f'{instrument}/positionBook', params={"time": time} if time else {})


# if __name__ == '__main__':
#     for i in ['US30_USD', 'GBP_USD']:
#         for g in ['M5']:
#             od = OandaInstrumentData()
#             od.write_candles_to_csv(
#                 instrument=i,
#                 granularity=g,
#                 output_loc=f'/Users/olliebakhtiari/Dropbox/My Mac (Ollie’s MacBook Air)/Documents/pagetpalace_backtester/pagetpalace_backtester/data/oanda/{i}/{i.strip("_")}_{g}.csv',
#                 start_year=2018,
#                 end_year=2021,
#                 prices='ABM',
#             )
#     od = OandaInstrumentData()
#     print(od.get_complete_candlesticks(instrument='XAU_USD', granularity='H1', count=3))
