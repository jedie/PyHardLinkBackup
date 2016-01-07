import shutil

import os
import logging
import configparser


log = logging.getLogger(__name__)
# logging.basicConfig(level=logging.DEBUG)

CONFIG_FILENAME="PyHardLinkBackup.ini"
DEAFULT_CONFIG_FILENAME="config_defaults.ini"


def get_dict_from_ini(filepath):
    log.debug("Read config %r" % filepath)
    parser = configparser.ConfigParser(interpolation=None)
    parser.read(filepath)
    config={}
    for section in parser.sections():
        config.update(
            dict(parser.items(section))
        )
    log.debug("readed config: %r" % config)
    return config


def get_user_ini_filepath():
    return os.path.join(os.path.expanduser("~"), CONFIG_FILENAME)


def get_ini_search_paths():
    search_paths=[
        os.path.join(os.getcwd(), CONFIG_FILENAME),
        get_user_ini_filepath()
    ]
    log.debug("Search paths: %r" % search_paths)
    return search_paths


def get_ini_filepath():
    search_paths=get_ini_search_paths()
    for filepath in search_paths:
        if os.path.isfile(filepath):
            return filepath


def get_config_dict():
    # Read the defaults
    default_config_filepath = os.path.join(
        os.path.dirname(__file__), DEAFULT_CONFIG_FILENAME
    )
    config = get_dict_from_ini(default_config_filepath)

    ini_filepath = get_ini_filepath()
    if not ini_filepath:
        # No .ini file made by user found
        # -> Create one into user home
        user_ini_filepath = get_user_ini_filepath()
        shutil.copyfile(default_config_filepath,user_ini_filepath)
        print("\n*************************************************************")
        print("Default config file was created into your home:")
        print("\t%s" % user_ini_filepath)
        print("Change it for your needs ;)")
        print("*************************************************************\n")
    else:
        print("\nread user configuration from:")
        print("\t%s\n" % ini_filepath)
        config.update(
            get_dict_from_ini(ini_filepath)
        )
        log.debug("Config changed to: %r" % config)

    return config


if __name__ == '__main__':
    from pprint import pprint

    d = get_config_dict()

    pprint(d)