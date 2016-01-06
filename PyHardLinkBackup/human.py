
def human_time(t):
    if t > 3600:
        divisor = 3600.0
        unit = "h"
    elif t > 60:
        divisor = 60.0
        unit = "min"
    else:
        divisor = 1
        unit = "sec"

    return "%.1f%s" % (round(t / divisor, 2), unit)