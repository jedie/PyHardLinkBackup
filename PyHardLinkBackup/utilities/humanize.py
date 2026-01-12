

def human_filesize(size: int | float) -> str:
    """
    >>> human_filesize(1024)
    '1.00 KiB'
    >>> human_filesize(2.2*1024)
    '2.20 KiB'
    >>> human_filesize(3.33*1024*1024)
    '3.33 MiB'
    >>> human_filesize(4.44*1024*1024*1024)
    '4.44 GiB'
    >>> human_filesize(5.55*1024*1024*1024*1024)
    '5.55 TiB'
    >>> human_filesize(6.66*1024*1024*1024*1024*1024)
    '6.66 PiB'
    """
    for unit in ['Bytes', 'KiB', 'MiB', 'GiB', 'TiB']:
        if size < 1024.0:
            return f'{size:.2f} {unit}'
        size /= 1024.0
    return f'{size:.2f} PiB'
