

def patch(filepath, debug):
    """
    replace 'pause' from windows batch.
    Needed for ci.appveyor.com
    see: https://github.com/appveyor/ci/issues/596
    """
    print("patch 'pause' in %r" % filepath)
    with open(filepath, "r") as infile:
        origin_content = infile.read()

    new_content = origin_content.replace("pause\n", """echo "'pause'"\n""")
    assert new_content!=origin_content, "not changed: %s" % origin_content

    with open(filepath, "w") as outfile:
        outfile.write(new_content)

    print("%r patched" % filepath)
    if debug:
        print("-"*79)
        print(repr(new_content))
        print("-"*79)
        print(new_content)
        print("-"*79)