# standardnotes-fs

## Description
Mount your [Standard Notes](https://standardnotes.org/) account as a filesystem and edit your notes as plain text files.

This allows you to edit your notes in your favorite text editor, use standard \*nix programs and Bash scripts to manipulate them, or back them up with rsync.

This is an _unofficial_ Standard Notes client.

## Example
```text
(env) $ python standardnotes_fs.py ~/notes
Please enter your Standard Notes username: tanner@example.com
Please enter your password (hidden): 

(env) $ tree ~/notes
/home/tanner/notes
├── Accounts.txt
├── Books.txt
├── Checklists.txt
├── Invention Ideas.txt
├── News Notes.txt
├── Shopping.txt
├── standardnotes-fs.txt
├── Todo.txt
└── Wifi.txt

0 directories, 31 files

(env) $ cat ~/notes/Todo.txt
V Get groceries
V Laundry
X Replace kitchen light
O Write standardnotes-fs readme
O Release standardnotes-fs

(env) $ fusermount -u ~/notes
```
## Usage
```text
usage: standardnotes_fs.py [-h] [--username USERNAME] [--password PASSWORD]
                           [-v] [--foreground] [--sync-sec SYNC_SEC]
                           [--sync-url SYNC_URL] [--no-config-file]
                           [--config CONFIG] [--logout]
                           [mountpoint]

positional arguments:
  mountpoint           local mountpoint folder

optional arguments:
  -h, --help           show this help message and exit
  --username USERNAME  Standard Notes username to log in with
  --password PASSWORD  Standard Notes password to log in with
                       NOTE: It is NOT recommended to use this option!
                             The password may be stored in history, so
                             use the password prompt instead.
  -v, --verbosity      output verbosity -v or -vv (implies --foreground)
  --foreground         run standardnotes-fs in the foreground
  --sync-sec SYNC_SEC  how many seconds between each sync. Default: 30
  --sync-url SYNC_URL  URL of Standard File sync server. Defaults to:
                       https://sync.standardnotes.org
  --no-config-file     don't load or create a config file
  --config CONFIG      specify a config file location. Defaults to:
                       /home/tanner/.config/standardnotes-fs/standardnotes-fs.conf
  --logout             delete login credentials saved in config and quit
```

## Installation
### For Debian/Ubuntu-based systems
Install dependencies:
```text
$ sudo apt-get install fuse python3 python3-pip virtualenv python3-virtualenv
```

Clone the repo and install Python Dependencies:
```text
$ git clone https://github.com/tannercollin/standardnotes-fs.git
$ cd standardnotes-fs/
$ virtualenv -p python3 env
$ . env/bin/activate
(env) $ pip install -r requirements.txt
(env) $ deactivate
$
```

Run standardnotes-fs:
```text
$ mkdir ~/notes
$ . env/bin/activate
(env) $ python standardnotes_fs.py ~/notes
(env) $
```

When you are finished, unmount:
```text
(env) $ fusermount -u ~/notes
(env) $ deactivate
$
```
## Notes
* Important: standardnotes-fs has not been tested vigorously yet. Before you use it, please make a backup of your notes by selecting `Account > Download Data Archive` in the official Standard Notes client.
* Your account password is not stored and the Python variable is deleted after your encryption keys are generated with it.
* Your account's encryption keys are stored in a config file on disk. This can be disabled with `--no-config-file`.
* By default the client syncs with the Standard Notes server every 30 seconds and after any note modifications are saved.
* If connection to the server is lost, it will keep trying to sync periodically.
* Filesystem functions currently supported: getattr, readdir, read, truncate, write, create, unlink, utimens, and rename.
* Creating hidden files (names beginning with a period) is disabled to prevent junk file creation.
* Notes with identical names are deduplicated by adding a number to the end.
* On the filesystem, notes will have the '.txt' extension appended to their name

## License
This program is free and open-source software licensed under the GNU GPLv3. Please see the `LICENSE` file for details.

That means you have the right to study, change, and distribute the software and source code to anyone and for any purpose as long as you grant the same rights when distributing it. You deserve these rights. Please take advantage of them because I like pull requests and would love to see this code put to use.

## Acknowledgements
Thanks to all the devs behind Standard Notes, Python, libfuse and FUSE.
