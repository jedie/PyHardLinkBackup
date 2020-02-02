"""
    Mock datetime.now()

    Based on https://gist.github.com/rbarrois/5430921 from Raphaël Barrois
"""

import datetime
from unittest import mock


def mock_datetime_now(target):

    real_datetime_class = datetime.datetime

    class DatetimeSubclassMeta(type):
        @classmethod
        def __instancecheck__(mcs, obj):
            return isinstance(obj, real_datetime_class)

    class BaseMockedDatetime(datetime.datetime):
        @classmethod
        def now(cls, tz=None):
            return target.replace(tzinfo=tz)

    return mock.patch.object(
        datetime, 'datetime',
        DatetimeSubclassMeta('datetime', (BaseMockedDatetime,), {})
    )


def test_datetime_mock():
    dt = datetime.datetime(
        year=2020, month=1, day=2, hour=3, minute=4, second=5, microsecond=6
    )
    with mock_datetime_now(dt):
        assert str(datetime.datetime.now()) == '2020-01-02 03:04:05.000006'
        assert isinstance(datetime.datetime.now(), datetime.datetime)
        assert isinstance(dt, datetime.datetime)
