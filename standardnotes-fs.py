import appdirs
import argparse
import logging
import os
import pathlib
import sys

from configparser import ConfigParser
from getpass import getpass

from api import StandardNotesAPI

OFFICIAL_SERVER_URL = 'https://sync.standardnotes.org'
APP_NAME = 'standardnotes-fs'
logging.basicConfig(level=logging.DEBUG)

# path settings
cfg_env = os.environ.get('SN_FS_CONFIG_PATH')
CONFIG_PATH = cfg_env if cfg_env else appdirs.user_config_dir(APP_NAME)
CONFIG_FILE = os.path.join(CONFIG_PATH, APP_NAME + '.conf')
CONFIG_FILE = pathlib.PurePath(CONFIG_PATH, APP_NAME + '.conf')

def parse_options():
    parser = argparse.ArgumentParser(formatter_class=argparse.RawTextHelpFormatter)
    parser.add_argument('--username',
                        help='Standard Notes username to log in with')
    parser.add_argument('--password',
                        help='Standard Notes password to log in with\n'
                             'NOTE: It is NOT recommended to use this! The\n'
                             '      password may be stored in history, so\n'
                             '      use the password prompt instead.')
    parser.add_argument('--sync-url',
                        help='URL of Standard File sync server. Defaults to:\n'
                        ''+OFFICIAL_SERVER_URL)
    parser.add_argument('--no-config-file', action='store_true',
                        help='Don\'t load or create a config file')
    parser.add_argument('--config',
                        help='Specify a config file location. Defaults to:\n'
                        ''+str(CONFIG_FILE))
    return parser.parse_args()

def main():
    args = parse_options()
    config = ConfigParser()
    config['DEFAULT'] = {}
    keys = {}

    if not args.no_config_file:
        config_file = args.config if args.config else CONFIG_FILE
        config_file = pathlib.Path(config_file)

        try:
            config_file.parent.mkdir(mode=0o0700, parents=True, exist_ok=True)
        except OSError:
            err_msg = 'Error creating directory "%s".'
            logging.critical(err_msg % str(config_file.parent))
            sys.exit(1)

        try:
            with config_file.open() as f:
                config.read_file(f)
        except OSError:
            err_msg = 'Config file "%s" not found.'
            logging.debug(err_msg % str(config_file))

    if config.has_option('user', 'sync_url'):
        sync_url = config.get('user', 'sync_url')
    else:
        sync_url = args.sync_url if args.sync_url else OFFICIAL_SERVER_URL

    if config.has_option('user', 'username') and config.has_section('keys'):
        username = config.get('user', 'username')
        keys = dict(config.items('keys'))
    else:
        username = args.username if args.username else \
                   input('Please enter your Standard Notes username: ')
        password = args.password if args.password else \
                   getpass('Please enter your password (hidden): ')

    sn_api = StandardNotesAPI(sync_url, username)
    if not keys:
        keys = sn_api.genKeys(password)
    sn_api.signIn(keys)

if __name__ == '__main__':
    main()
