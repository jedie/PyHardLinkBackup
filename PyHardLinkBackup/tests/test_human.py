
"""
    e.g.:

"""
import datetime

from django.contrib.humanize.templatetags import humanize
from django.utils import translation
import django

from PyHardLinkBackup.phlb import human


#------------------------------------------------------------------------------
# from https://github.com/django/django/blob/master/tests/humanize_tests/tests.py
now = datetime.datetime(2012, 3, 9, 22, 30)

class MockDateTime(datetime.datetime):
    @classmethod
    def now(cls, tz=None):
        if tz is None or tz.utcoffset(now) is None:
            return now
        else:
            # equals now.replace(tzinfo=utc)
            return now.replace(tzinfo=tz) + tz.utcoffset(now)

#------------------------------------------------------------------------------



class HumanTestCase(django.test.SimpleTestCase):

    def test_ns2naturaltimesince(self):
        orig_humanize_datetime, humanize.datetime = humanize.datetime, MockDateTime
        try:
            timestamp = now - datetime.timedelta(hours=23, minutes=50, seconds=50)
            ns = timestamp.timestamp() * 1000000000

            # FIXME: why not "hours ago" translated ?!?
            with translation.override("de"):
                self.assertEqual(
                    human.ns2naturaltimesince(ns),
                    "8. März 2012 22:39 (23 hours ago)"
                )

            with translation.override('en'):
                self.assertEqual(
                    human.ns2naturaltimesince(ns),
                    "March 8, 2012, 10:39 p.m. (23 hours ago)"
                )

        finally:
            humanize.datetime = orig_humanize_datetime

