# Python standard.
import calendar
import datetime


class TradingSessionValidator:
    _GMT_OPENING_HOURS = [8, 12, 16]
    _BST_OPENING_HOURS = [9, 13, 17]

    def __init__(self, date_time: datetime.datetime):
        self.date_time = date_time
        self._openings_hours = self._get_openings_hours()

    def __repr__(self):
        return f'TradingSessionValidator(self.date_time={self._date_time}, self._opening_hours={self._openings_hours})'

    @property
    def date_time(self):
        return self._date_time

    @date_time.setter
    def date_time(self, value):
        if not isinstance(value, datetime.datetime):
            raise TypeError('Invalid date_time given, must be of type datetime.datetime.')
        self._date_time = value
        self._openings_hours = self._get_openings_hours()

    def _get_openings_hours(self):
        return self._GMT_OPENING_HOURS if self._is_dt_within_daylight_savings_period() else self._BST_OPENING_HOURS

    def _is_dt_within_daylight_savings_period(self) -> bool:
        march = calendar.monthcalendar(self.date_time.year, 3)
        october = calendar.monthcalendar(self.date_time.year, 10)

        return datetime.datetime(self.date_time.year, 3, max(march[-1][calendar.SUNDAY], march[-2][calendar.SUNDAY])) \
            <= self.date_time \
            < datetime.datetime(self.date_time.year, 10, max(october[-1][calendar.SUNDAY], october[-2][calendar.SUNDAY]))

    def is_new_session(self) -> bool:
        return self.date_time.hour in self._openings_hours and self.date_time.minute == 0

    def is_within_trading_hours(self, close_time_offset: int = 0) -> bool:
        return self._openings_hours[0] <= self.date_time.hour < self._openings_hours[-1] + 5 + close_time_offset
