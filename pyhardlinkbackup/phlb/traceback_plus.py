"""
    Based on code from:
    https://code.google.com/p/scite-files/wiki/Customization_PythonDebug
    http://code.activestate.com/recipes/52215/
"""


import sys
import traceback

try:
    import click
except ImportError as err:
    msg = f"Import error: {err} - Please install 'click' !"
    raise ImportError(msg)

MAX_CHARS = 256


def print_exc_plus():
    sys.stderr.flush()  # for eclipse/PyCharm
    sys.stdout.flush()  # for eclipse/PyCharm
    for line in exc_plus():
        print(line)


def exc_plus():
    """
    Print the usual traceback information, followed by a listing of all the
    local variables in each frame.
    """
    tb = sys.exc_info()[2]
    while True:
        if not tb.tb_next:
            break
        tb = tb.tb_next
    stack = []
    f = tb.tb_frame
    while f:
        stack.append(f)
        f = f.f_back

    txt = traceback.format_exc()
    txt_lines = txt.splitlines()
    first_line = txt_lines.pop(0)
    last_line = txt_lines.pop(-1)
    yield click.style(first_line, fg="red")
    for line in txt_lines:
        if line.strip().startswith("File"):
            yield line
        else:
            yield click.style(line, fg="white", bold=True)
    yield click.style(last_line, fg="red")
    yield click.style("\nLocals by frame, most recent call first:", fg="blue", bold=True)
    for frame in stack:
        msg = f'File "{frame.f_code.co_filename}", line {frame.f_lineno:d}, in {frame.f_code.co_name}'
        msg = click.style(msg, fg="white", bold=True, underline=True)
        yield f"\n *** {msg}"

        for key, value in list(frame.f_locals.items()):
            key_info = "%30s = " % click.style(key, bold=True)
            # We have to be careful not to cause a new error in our error
            # printer! Calling str() on an unknown object could cause an
            # error we don't want.
            if isinstance(value, int):
                value = f"${value:x} (decimal: {value:d})"
            else:
                value = repr(value)

            if len(value) > MAX_CHARS:
                value = f"{value[:MAX_CHARS]}..."

            try:
                yield key_info + value
            except BaseException:
                yield key_info + " <ERROR WHILE PRINTING VALUE>"
