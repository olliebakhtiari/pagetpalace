# Python standard.
from typing import Tuple, Union

# Third-party.
import numpy as np
import pandas as pd


def moving_average(values: list, window):
    weights = np.repeat(1.0, window) / window
    smas = np.convolve(values, weights, 'valid')

    return smas


def exp_moving_average(values, window):
    weights = np.exp(np.linspace(-1., 0., window))
    weights /= weights.sum()
    a = np.convolve(values, weights, mode='full')[:len(values)]
    a[:window] = a[window]

    return a


def append_ssma(df: pd.DataFrame, periods: int = 50, column: str = "midClose", adjust: bool = True):
    df[f'SSMA{periods}'] = df[column].ewm(ignore_na=False, alpha=1.0 / periods, min_periods=0, adjust=adjust).mean()


def momentum_line(data, prices: str, time_period: int = 10):
    """ Takes list of data points and produces an exponential moving average.

            https://www.tradingview.com/wiki/Moving_Average

        There are three steps to calculate the EMA. Here is the formula for a 5 Period EMA:
            1. Calculate the SMA

            (Period Values / Number of Periods)

            2. Calculate the Multiplier

            (2 / (Number of Periods + 1) therefore (2 / (5+1) = 33.333%

            3. Calculate the EMA

            For the first EMA, we use the SMA(previous day) instead of EMA(previous day).

            EMA = {Close - EMA(previous day)} x multiplier + EMA(previous day)
    """
    s = 0
    for val in range(time_period - 1):
        s += data[f'{prices}Open'][val]
    simple_avg = s / time_period
    ema = [simple_avg]
    alpha = 2 / (time_period + 1)
    data = data[f'{prices}Open']
    for i in range(len(data)):
        ema.append((data[i] - ema[-1]) * alpha + ema[-1])
    ema = pd.Series(ema[1:], index=data.index).shift(1)

    return ema


def get_supports_and_resistances(data: pd.DataFrame, prices: str) -> dict:
    """ Calculated based off of the pivot point.

        The pivot point and associated support and resistance levels are calculated by using the last trading session’s
        open, high, low, and close.

        The calculation for a pivot point is shown below:

            - Pivot point (PP) = (High + Low + Close) / 3

        Support and resistance levels are then calculated off the pivot point like so:

            First level support and resistance:

                - First resistance (R1) = (2 x PP) – Low

                - First support (S1) = (2 x PP) – High

            Second level of support and resistance:

                - Second resistance (R2) = PP + (High – Low)

                - Second support (S2) = PP – (High – Low)

            Third level of support and resistance:

                - Third resistance (R3) = High + 2(PP – Low)

                - Third support (S3) = Low – 2(High – PP)
    """
    supports_and_resistances = {}

    high = data[f'{prices}High']
    low = data[f'{prices}Low']
    close = data[f'{prices}Close']

    pivot_point = (high + low + close) / 3

    supports_and_resistances['s1'] = (2 * pivot_point) - high
    supports_and_resistances['r1'] = (2 * pivot_point) - low

    supports_and_resistances['s2'] = pivot_point - (high - low)
    supports_and_resistances['r2'] = pivot_point + (high - low)

    supports_and_resistances['s3'] = low - 2 * (high - pivot_point)
    supports_and_resistances['r3'] = high - 2 * (high - pivot_point)

    return {k: round(v, 4) for k, v in supports_and_resistances.items()}


def compute_macd(x, slow=26, fast=12):
    """ Moving Average Convergence Divergence (MACD) is a trend-following momentum indicator that shows the relationship
        between two moving averages of a security’s price. The MACD is calculated by subtracting the 26-period
        Exponential Moving Average (EMA) from the 12-period EMA.

        - MACD is calculated by subtracting the 26-period EMA from the 12-period EMA.
        - MACD triggers technical signals when it crosses above (to buy) or below (to sell) its signal line.
        - The speed of crossovers is also taken as a signal of a market is overbought or oversold.
        - MACD helps investors understand whether the bullish or bearish movement in the price is strengthening
          or weakening.

    :param x:
    :param slow:
    :param fast:
    :return: 3 EMA's.
    """
    ema_slow = exp_moving_average(x, slow)
    ema_fast = exp_moving_average(x, fast)

    return ema_slow, ema_fast, ema_fast - ema_slow


def relative_strength_index(prices, periods=14):
    """ Momentum indicator that measures the magnitude of recent price changes to evaluate overbought or oversold
        conditions in the price of a stock or other asset. The RSI is displayed as an oscillator
        (a line graph that moves between two extremes) and can have a reading from 0 to 100.

        - Signals are considered overbought when the indicator is above 70% and
          oversold when the indicator is below 30%.

    :param prices:
    :param periods:
    :return: RSI.
    """
    deltas = np.diff(prices)
    seed = deltas[:periods + 1]
    up = seed[seed >= 0].sum() / periods
    down = -seed[seed < 0].sum() / periods
    rs = up / down
    rsi_val = np.zeros_like(prices)
    rsi_val[:periods] = 100. - 100. / (1. + rs)
    for i in range(periods, len(prices)):
        delta = deltas[i - 1]
        if delta > 0:
            up_val = delta
            down_val = 0.
        else:
            up_val = 0.
            down_val = -delta
        up = (up * (periods - 1) + up_val) / periods
        down = (down * (periods - 1) + down_val) / periods
        rs = up / down
        rsi_val[i] = 100. - 100. / (1. + rs)

    return rsi_val


def stochastic_oscillator(close_prices, highs, lows, smooth_k: int, smooth_d: int, periods: int):
    """ Momentum indicator comparing the closing price of a security to the range of its prices over a certain period
        of time. The sensitivity of the oscillator to market movements is reducible by adjusting that time period or by
        taking a moving average of the result.

                                            %K = 100(C – L14)/(H14 – L14)

        where...
            - C = the most recent closing price
            - L14 = the low of the 14 previous trading sessions
            - H14 = the highest price traded during the same 14-day period
            - %K= the current market rate for the currency pair
            - %D = 3-period moving average of %K

        Transaction signals are created when the %K crosses through a three-period moving average,
        which is called the %D.

    :return: %k, %d.
    """
    lowest_low = pd.Series.rolling(lows, window=periods, center=False).min()
    highest_high = pd.Series.rolling(highs, window=periods, center=False).max()
    k = pd.Series.rolling(100 * ((close_prices - lowest_low) / (highest_high - lowest_low)), window=smooth_k).mean()
    d = pd.Series.rolling(k, window=smooth_d).mean()

    return k, d


def stochastic_rsi(prices, periods: int, smooth_k: int, smooth_d: int):
    p = prices.reset_index(drop=True)
    delta = p.diff().dropna()
    ups = delta * 0
    downs = ups.copy()
    ups[delta > 0] = delta[delta > 0]
    downs[delta < 0] = -delta[delta < 0]
    ups[ups.index[periods - 1]] = np.mean(ups[:periods])
    ups = ups.drop(ups.index[:(periods - 1)])
    downs[downs.index[periods - 1]] = np.mean(downs[:periods])
    downs = downs.drop(downs.index[:(periods - 1)])
    rs = (
            ups.ewm(com=periods - 1, min_periods=0, adjust=False, ignore_na=False).mean()
            / downs.ewm(com=periods - 1, min_periods=0, adjust=False, ignore_na=False).mean()
    )
    rsi = 100 - 100 / (1 + rs)
    stoch_rsi = (rsi - rsi.rolling(periods).min()) / (rsi.rolling(periods).max() - rsi.rolling(periods).min())
    stoch_rsi_k = stoch_rsi.rolling(smooth_k).mean()
    stoch_rsi_d = stoch_rsi_k.rolling(smooth_d).mean()

    return stoch_rsi.to_frame(), stoch_rsi_k.to_frame(), stoch_rsi_d.to_frame()


def ssl_channel(data: pd.DataFrame,
                prices: str = 'mid',
                periods: int = 20) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    close_prices = data[f'{prices}Close'].reset_index(drop=True)
    high_sma = data[f'{prices}High'].rolling(window=periods).mean()
    low_sma = data[f'{prices}Low'].rolling(window=periods).mean()
    hi_lo_vals = np.array([0 for _ in range(len(close_prices))])
    for i in range(len(high_sma)):
        if close_prices[i] > high_sma[i]:
            hi_lo_vals[i] = 1
        elif close_prices[i] < low_sma[i]:
            hi_lo_vals[i] = -1
        else:
            hi_lo_vals[i] = hi_lo_vals[i - 1]
    ssl_down = np.array([high_sma[i] if hi_lo_vals[i] < 0 else low_sma[i] for i in range(len(high_sma))])
    ssl_up = np.array([low_sma[i] if hi_lo_vals[i] < 0 else high_sma[i] for i in range(len(high_sma))])

    return hi_lo_vals, ssl_down, ssl_up


def get_ssl_value(df: pd.DataFrame, prices: str = 'mid') -> Union[int, None]:
    close = df[f'{prices}Close'].apply(pd.to_numeric).iloc[-1]
    if close > df[f'{prices}High'].apply(pd.to_numeric).mean():
        return 1
    if close > df[f'{prices}Low'].apply(pd.to_numeric).mean():
        return -1


def append_ssl_channel(data: pd.DataFrame, periods: int = 20):
    hlv, ssl_down, ssl_up = ssl_channel(data, periods=periods)
    data['HighLowValue'] = hlv
    data['SSLDown'] = ssl_down
    data['SSLUp'] = ssl_up


def true_range(today_date, high, low, yesterday_close_price):
    x = high - low
    y = abs(high - yesterday_close_price)
    z = abs(low - yesterday_close_price)
    if y <= x >= z:
        tr = x
    elif x <= y >= z:
        tr = y
    elif x <= z >= y:
        tr = z
    else:
        tr = 0

    return today_date, tr


def average_true_range(data, time_frame):
    tr_dates = []
    trs = []
    for i in range(1, len(data)):
        row = data.iloc[i]
        date, _time = str(row[0]).split()
        tr_date, tr = true_range(
            today_date=date,
            high=row[2],
            low=row[3],
            yesterday_close_price=data.iloc[i - 1][4]
        )
        tr_dates.append(tr_date)
        trs.append(tr)

    return exp_moving_average(trs, time_frame)


def directional_movement(date, high, low, y_high, y_low):
    move_up = high - y_high
    move_down = y_low - low
    if 0 < move_up > move_down:
        pos_dm = move_up
    else:
        pos_dm = 0

    if 0 < move_down > move_up:
        neg_dm = move_down
    else:
        neg_dm = 0

    return date, pos_dm, neg_dm


def calculate_directional_index(data):
    tr_dates = []
    trs = []
    pos_dms = []
    neg_dms = []
    for i in range(1, len(data)):
        # extract data
        row = data.iloc[i]
        date, _time = str(row[0]).split()
        high = row[2]
        low = row[3]
        y_high = data.iloc[i - 1][2]
        y_low = data.iloc[i - 1][3]
        y_close = data.iloc[i - 1][4]

        # calculate true ranges
        tr_date, tr = true_range(
            today_date=date,
            high=high,
            low=low,
            yesterday_close_price=y_close
        )
        tr_dates.append(tr_date)
        trs.append(tr)

        # calculate directional movement
        dm_date, pos_dm, neg_dm = directional_movement(
            date=date,
            high=high,
            low=low,
            y_high=y_high,
            y_low=y_low,
        )
        pos_dms.append(pos_dm)
        neg_dms.append(neg_dm)

    # exponentials
    exp_pos_dm = exp_moving_average(pos_dms, 14)
    exp_neg_dm = exp_moving_average(neg_dms, 14)
    atr = exp_moving_average(trs, 14)

    # directional indexes
    x = 0
    pdis = []
    ndis = []
    while x < len(atr):
        # positives
        pdi = 100 * (exp_pos_dm[x] / atr[x])
        pdis.append(pdi)

        # negatives
        ndi = 100 * (exp_neg_dm[x] / atr[x])
        ndis.append(ndi)
        x += 1

    return pdis, ndis


def average_directional_index(data):
    """ - Designed by Welles Wilder for commodity daily charts, but can be used in other markets or other timeframes.
        - The price is moving up when +DI is above -DI, and the price is moving down when -DI is above +DI.
        - Crosses between +DI and -DI are potential trading signals as bears or bulls gain the upper hand.
        - The trend has strength when ADX is above 25. The trend is weak or the price is trendless when ADX is below 20,
          according to Wilder.
        - Non-trending doesn't mean the price isn't moving. It may not be, but the price could also be making a trend
          change or is too volatile for a clear direction to be present.

    :param data:
    :return: adx.
    """
    positive_di, negative_di = calculate_directional_index(data)
    x = 0
    dxs = []
    while x < len(positive_di):
        dx = 100 * (abs(positive_di[x] - negative_di[x]) / (positive_di[x] + negative_di[x]))
        dxs.append(dx)
        x += 1
    adx = exp_moving_average(dxs, 14)

    return adx


def aroon(data, time_frame):
    """ Identify trend changes in the price of an asset, as well as the strength of that trend. In essence,
        the indicator measures the time between highs and the time between lows over a time period. The idea
        is that strong uptrends will regularly see new highs, and strong downtrends will regularly see new lows.
        The indicator signals when this is happening, and when it isn't.

        The indicator consists of the "Aroon up" line, which measures the strength of the uptrend, and the "Aroon down"
        line, which measures the strength of the downtrend.

        - The Arron indicator is composed of two lines. An up line which measures the number of periods since a High,
          and a down line which measures the number of periods since a Low.
        - The indicator is typically applied to 25 periods of data, so the indicator is showing how many periods it has
          been since a 25-period high or low.
        - When the Aroon Up is above the Aroon Down, it indicates bullish price behavior.
        - When the Aroon Down is above the Aroon Up, it signals bearish price behavior.
        - Crossovers of the two lines can signal trend changes. For example, when Aroon Up crosses above Aroon Down it
          may mean a new uptrend is starting.
        - The indicator moves between zero and 100. A reading above 50 means that a high/low
          (whichever line is above 50) was seen within the last 12 periods.
        - A reading below 50 means that the high/low was seen within the 13 periods.

    :param data:
    :param time_frame:
    :return: dates, up values, down values.
    """
    aro_ups = []
    aro_downs = []
    aro_dates = []
    x = time_frame
    while x < len(data):
        date, _time = str(data['Gmt time'][x]).split()
        high = data['High']
        low = data['Low']
        aroon_up = ((high[x - time_frame:x].tolist().index(max(high[x - time_frame:x]))) / float(time_frame)) * 100
        aroon_down = ((low[x - time_frame:x].tolist().index(min(low[x - time_frame:x]))) / float(time_frame)) * 100
        aro_ups.append(aroon_up)
        aro_downs.append(aroon_down)
        aro_dates.append(date)
        x += 1

    return aro_dates, aro_ups, aro_downs


def chaikin_money_flow(data, time_frame):
    """ Oscillator that measures buying and selling pressure over a set period of time

        The calculation for Chaikin Money Flow (CMF) has three distinct steps
        (for this example we will use a 21 Period CMF):

        1. Find the Money Flow Multiplier
           [(Close  -  Low) - (High - Close)] /(High - Low) = Money Flow Multiplier

        2. Calculate Money Flow Volume
           Money Flow Multiplier x Volume for the Period = Money Flow Volume

        3. Calculate The CMF
           21 Period Sum of Money Flow Volume / 21 Period Sum of Volume = 21 Period CMF

    :param data: the instrument.
    :param time_frame: period.
    :return: dates, chaikin money flow values.
    """
    chmf = []
    mf_mults = []
    mf_vols = []
    x = time_frame
    date = data['Gmt time']
    high = data['High']
    low = data['Low']
    volume = data['Volume']
    close_price = data['Close']
    while x < len(data):
        period_volume = 0
        vol_range = volume[x - time_frame:x]
        for vol in vol_range:
            period_volume += vol
        cp = float(close_price[x])
        lo = float(low[x])
        hi = float(high[x])
        if cp == hi and cp == lo or hi == lo:
            mfm = 0
        else:
            mfm = ((cp - lo) - (hi - cp)) / (hi - lo)
        mfv = mfm * period_volume
        mf_mults.append(mfm)
        mf_vols.append(mfv)
        x += 1
    y = time_frame
    while y < len(mf_vols):
        period_volume = 0
        vol_range = volume[x - time_frame:x]
        for vol in vol_range:
            period_volume += vol
        consider = mf_vols[y - time_frame:y]
        tfs_mfv = 0
        for mfv in consider:
            tfs_mfv += mfv
        tfs_cmf = tfs_mfv / period_volume
        chmf.append(tfs_cmf)
        y += 1

    return date[time_frame + time_frame:], chmf


def chande_momentum_oscillator(dates, prices, time_frame):
    """ The formula calculates the difference between the sum of recent gains and the sum of recent losses and then
        divides the result by the sum of all price movement over the same period.

        - The chosen time frame greatly affects signals.
        - Pattern recognition often generates more reliable signals than absolute oscillator levels.
        - Overbought-oversold indicators are less effective in strongly-trending markets.

    :param dates:
    :param prices:
    :param time_frame:
    :return: dates, chande momentum oscillator values.
    """
    cmo = []
    x = time_frame
    while x < len(prices):
        consideration_prices = prices[x - time_frame: x].values
        up_sum = 0
        down_sum = 0
        y = 1
        while y < time_frame:
            curr_price = consideration_prices[y]
            prev_price = consideration_prices[y - 1]
            if curr_price >= prev_price:
                up_sum += (curr_price - prev_price)
            else:
                down_sum += (prev_price - curr_price)
            y += 1
        curr_cmo = ((up_sum - down_sum) / (up_sum + float(down_sum))) * 100.00
        cmo.append(curr_cmo)
        x += 1

    return dates[time_frame:], cmo


def standard_deviation(prices, dates, time_frame):
    """ 1. Find average.
        2. Find variance, first calculate the difference from the mean, then square it.
        3. Add up each numbers variance, then divide by total number of numbers - 1.
        4. Square root step 3.

    :param prices:
    :param dates:
    :param time_frame:
    :return: standard deviation of given array of numbers.
    """
    sd = []
    sd_dates = []
    x = time_frame
    while x < len(prices):
        arr_to_consider = prices[x - time_frame:x]
        st_dev = arr_to_consider.std()
        sd.append(st_dev)
        sd_dates.append(dates[x])
        x += 1

    return sd_dates, sd


def bollinger_bands(data, prices_to_use, multiplier, time_frame):
    """ There are three lines that compose Bollinger Bands: A simple moving average (middle band) and an upper and
        lower band. The upper and lower bands are typically 2 standard deviations +/- from a 20-day simple moving
        average, but can be modified.

        BOLU=MA(TP,n)+m∗σ[TP,n]
        BOLD=MA(TP,n)−m∗σ[TP,n]

        where...
                - BOLU=Upper Bollinger Band
                - BOLD=Lower Bollinger Band
                - MA=Moving average
                - TP (typical price)=(High+Low+Close)÷3
                - n=Number of days in smoothing period (typically 20)
                - m=Number of standard deviations (typically 2)
                - σ[TP,n]=Standard Deviation over last n periods of TP

    :param data:
    :param prices_to_use:
    :param multiplier: typically 2.
    :param time_frame:
    :return: 3 ma's: top band, bottom band and middle band.
    """
    d = data[prices_to_use]
    middle_band = d.rolling(time_frame).mean()
    top_band = middle_band + d.rolling(time_frame).std() * multiplier
    bottom_band = middle_band - d.rolling(time_frame).std() * multiplier

    return top_band, bottom_band, middle_band


def elder_force_index(dates, close_prices, volumes, time_frame):
    """ Oscillator that measures the force, or power, of bulls behind particular market rallies and of bears behind
        every decline.

        The three key components of the force index are the direction of price change, the extent of the price change,
        and the trading volume. When the force index is used in conjunction with a moving average, the resulting figure
        can accurately measure significant changes in the power of bulls and bears.

                                        EFI = Close - Previous Close * Volume

        Then, an EMA is applied to the line, usually a ~14 day period EMA is used.

    :return: dates, elder force index for given time frames.
    """
    efi = []
    x = 1
    while x < len(close_prices):
        force_index = (close_prices[x] - close_prices[x - 1]) * volumes[x]
        efi.append(force_index)
        x += 1
    efi_tf = exp_moving_average(efi, time_frame)

    return dates[1:], efi_tf


def ichimoku_kinko_hyo(highs, lows, close_prices):
    """ 1 – Tenkan-Sen line, also called the Conversion Line, represents the midpoint of the last 9 candlesticks.
            It’s calculated by adding the highest high and the lowest low over the past nine periods and then dividing
            the result by two.
        2 – Kijun-Sen line, also called the Base Line, represents the midpoint of the last 26 candlesticks.
            It’s calculated in a similar fashion to the Tenkan-Sen line however we use the last 26 candlesticks as
            mentioned rather than the last 9 – just add the highest high and the lowest low over the past 26 periods
            and then divide the result by two.
        3 – Chiou Span, also called the Lagging Span, lags behind the price (as the name suggests).
            The Lagging Span is plotted 26 periods back.
        4 – Senkou Span A, also called the Leading Span A, represents one of the two Cloud boundaries and it’s the
            midpoint between the Conversion Line (Tenkan-Sen) and the Base Line (Kijun-Sen). It’s calculated by adding
            the Tenkan-Sen line and the Kijun-Sen line together and dividing by 2. This value is plotted 26 periods into
            the future and it’s the faster Cloud boundary.
        5 – Senkou Span B, or the Leading Span B, represents the second Cloud boundaries and it’s the midpoint of the
            last 52 price bars. Add the highest high and the lowest low over the past 52 periods and then divide the
            result by two. This value is plotted 26 periods into the future and it’s the slower Cloud boundary.

    :return:
    """
    nine_period_high = highs.rolling(9).max()
    nine_period_low = lows.rolling(9).min()
    tenkan_sen = (nine_period_high + nine_period_low) / 2

    twenty_six_period_high = highs.rolling(26).max()
    twenty_six_period_low = lows.rolling(26).min()
    kijun_sen = (twenty_six_period_high + twenty_six_period_low) / 2

    senkou_span_a = ((tenkan_sen + kijun_sen) / 2).shift(26)

    fifty_two_period_high = highs.rolling(52).max()
    fifty_two_period_low = lows.rolling(52).min()
    senkou_span_b = ((fifty_two_period_high + fifty_two_period_low) / 2).shift(26)

    chikou_span = close_prices.shift(-26)

    return tenkan_sen, kijun_sen, senkou_span_a, senkou_span_b, chikou_span


def keltner_channels(data, time_frame_one, time_frame_two):
    """ Volatility based technical indicator composed of three separate lines. The middle line is an exponential moving
        average (EMA) of the price. Additional lines are placed above and below the EMA. The upper band is typically
        set two times the Average True Range (ATR) above the EMA, and lower band is typically set two times the ATR
        below the EMA. The bands expand and contract as volatility (measured by ATR) expands and contracts.

        - The EMA of a Keltner Channel is typically 20 periods, although this can be adjusted if desired.
        - The upper and lower bands are typically set two times the ATR above and below the EMA, although the multiplier
          can also be adjusted based on personal preference. A larger multiplier will result in a wider channel.
        - Price reaching the upper band is bullish, while reaching the lower band is bearish. Reaching a band may
          indicate a continued trend in that direction.
        - The angle of the channel also aids in identifying the trend direction. When the channel is angled upwards,
          the price is rising. When the channel is angled downward the price is falling. If the channel is moving
          sideways, the price has been as well.
        - The price may also oscillate between the upper and lower bands. When this happens, the upper band is viewed
          as resistance and the lower band is support.

                                        Keltner Channel Middle Line=EMA
                                        Keltner Channel Upper Band=EMA+2∗ATR
                                        Keltner Channel Lower Band=EMA−2∗ATR

        where...
                EMA=Exponential moving average (typically over 20 periods)
                ATR=Average True Range (typically over 10 or 20 periods)
​
    :return:
    """
    middle_lines = []
    upper_bands = []
    lower_bands = []
    atr = average_true_range(data, time_frame_two)
    tf_ema = exp_moving_average(data['Close'], time_frame_one)[1:]
    x = 0
    while x < len(tf_ema):
        curr_ub = tf_ema[x] + (2 * atr[x])
        curr_ml = tf_ema[x]
        curr_lb = tf_ema[x] - (2 * atr[x])
        upper_bands.append(curr_ub)
        middle_lines.append(curr_ml)
        lower_bands.append(curr_lb)
        x += 1

    return upper_bands, middle_lines, lower_bands


def stochastic_signal(k: float, d: float, long_k_d: Tuple[float, float], short_k_d: Tuple[float, float]) -> str:
    """

    :param k: fast.
    :param d: slow.
    :param long_k_d: threshold for long trades (k, d).
    :param short_k_d: threshold for short trades (k, d).
    :return: long, short or undetermined.
    """
    if k > d and (k <= long_k_d[0] and d <= long_k_d[1]):
        return 'long'
    elif k < d and (k >= short_k_d[0] and d >= short_k_d[1]):
        return 'short'
    else:
        return 'undetermined'


def calculate_local_high_and_low(data: pd.DataFrame, current_index: int, look_back: int) -> Tuple[float, float]:
    high = float(0)
    low = float(1000)
    i = current_index
    while i > current_index - look_back and i >= 0:
        if data['AskHigh'][i] > high:
            high = data['AskHigh'][i]
        if data['AskLow'][i] < low:
            low = data['AskLow'][i]
        i -= 1

    return high, low


def trend_signal(data: pd.DataFrame, curr_idx: int, look_back: int) -> str:
    if curr_idx < 1:
        return 'undetermined'
    local_high, local_low = calculate_local_high_and_low(data, curr_idx, look_back)
    current_candlestick_open = data['AskOpen'][curr_idx]
    previous_candlestick_close = data['AskClose'][curr_idx - 1]
    if previous_candlestick_close <= local_low or current_candlestick_open <= local_low:
        direction = 'bearish'
    elif previous_candlestick_close >= local_high or current_candlestick_open >= local_high:
        direction = 'bullish'
    else:
        direction = 'undetermined'

    return direction


def momentum_line_signal(price: float, momentum_value: float) -> str:
    if price > momentum_value:
        return 'bullish'
    elif price < momentum_value:
        return 'bearish'
    else:
        return 'undetermined'


def distance_to_supp_and_res(entry: float, supp_and_res: dict, level: int = 3) -> Tuple[float, float]:
    """ Avoid taking long positions close to resistances, avoid taking short positions close to supports. Calculates
        distance from closest support or resistance.

    :param entry: potential entry price.
    :param supp_and_res:
    :param level:
    :return: tuple of (resistance-distance, support-distance).
    """
    if level > 3:
        raise ValueError('level must be 1, 2 or 3.')
    return abs(round(supp_and_res[f'r{level}'] - entry, 4)), abs(round(entry - supp_and_res[f's{level}'], 4))


def append_average_true_range(df: pd.DataFrame, prices: str = 'mid', periods: int = 14):
    data = df.copy()
    data.reset_index(drop=True)
    high = data[f'{prices}High'].apply(pd.to_numeric)
    low = data[f'{prices}Low'].apply(pd.to_numeric)
    close = data[f'{prices}Close'].apply(pd.to_numeric)
    data['tr0'] = abs(high - low)
    data['tr1'] = abs(high - close.shift())
    data['tr2'] = abs(low - close.shift())
    data['true_range'] = data[['tr0', 'tr1', 'tr2']].max(axis=1)

    df['ATR'] = data['true_range'].ewm(alpha=1 / periods).mean()
