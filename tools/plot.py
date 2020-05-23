# Python standard.
import datetime
from typing import List

# Third-party.
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import pandas as pd


def plot_overlay_balance_and_ssl(
        datetimes: pd.DataFrame,
        opens: pd.DataFrame,
        highs: pd.DataFrame,
        lows: pd.DataFrame,
        closes: pd.DataFrame,
        account_balance_over_time: List[float],
        ssl_ups: pd.DataFrame,
        ssl_downs: pd.DataFrame,
):
    fig = make_subplots(specs=[[{"secondary_y": True}]])
    fig.update_layout(title_text="Price data, account balance and SSL channel", xaxis_rangeslider_visible=True)
    fig.add_trace(
        go.Candlestick(
            x=datetimes,
            open=opens,
            high=highs,
            low=lows,
            close=closes,
            name="Candlestick data",
        ),
        secondary_y=False,
    )
    fig.add_trace(
        go.Scatter(
            x=datetimes,
            y=account_balance_over_time,
            mode="lines+markers",
            line={"color": "purple"},
            name="Account balance over time",
            ),
        secondary_y=True,
    )
    fig.add_trace(
        go.Scatter(
            x=datetimes,
            y=ssl_ups,
            mode="lines",
            line={"color": "green", "width": 1},
            name="SSL Ups",
            ),
        secondary_y=False,
    )
    fig.add_trace(
        go.Scatter(
            x=datetimes,
            y=ssl_downs,
            mode="lines",
            line={"color": "red", "width": 1},
            name="SSL Downs",
            ),
        secondary_y=False,
    )

    # Shared x-axis.
    fig.update_xaxes(title_text="datetime")

    # Dual y axes.
    fig.update_yaxes(title_text="Instrument price", secondary_y=False)
    fig.update_yaxes(title_text="Account balance (£)")

    fig.show()

