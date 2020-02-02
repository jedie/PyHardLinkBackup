import datetime

from django.contrib.humanize.templatetags import humanize
from django.template import defaultfilters
from django.utils.translation import ugettext as _


def to_percent(part, total):
    try:
        return part / total * 100
    except ZeroDivisionError:
        # e.g.: Backup only 0-Bytes files ;)
        return 0


def dt2naturaltimesince(dt):
    """
    datetime to a human readable representation with how old this entry is information
    e.g.:
        Jan. 27, 2016, 9:04 p.m. (31 minutes ago)
    """
    date = defaultfilters.date(dt, _("DATETIME_FORMAT"))
    nt = humanize.naturaltime(dt)
    return f"{date} ({nt})"


def ns2naturaltimesince(ns):
    """
    nanoseconds to a human readable representation with how old this entry is information
    e.g.:
        Jan. 27, 2016, 9:04 p.m. (31 minutes ago)
    """
    timestamp = ns / 1000000000
    dt = datetime.datetime.utcfromtimestamp(timestamp)
    return dt2naturaltimesince(dt)
