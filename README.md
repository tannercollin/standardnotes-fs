# standardnotes-fs

## Description
Mount your [Standard Notes](https://standardnotes.org/) account as a filesystem and edit your notes as plain text files.

This allows you to edit your notes in your favorite text editor, use standard \*nix programs and Bash scripts to manipulate them, or back them up with rsync.

This is an _unofficial_ Standard Notes client.

## Example

```text
$ snfs notes/
Please enter your Standard Notes username: tanner@example.com
Please enter your password (hidden): 
Enter your two-factor authentication code: 123456

$ tree --dirsfirst notes/
/home/tanner/notes
├── archived
│   └── old_notes.txt
├── tags
│   ├── lists
│   │   ├── Shopping.txt
│   │   └── Todo.txt
│   └── projects
│       └── standardnotes-fs.txt
├── trash
│   ├── loveletter.txt
│   └── renovations.txt
├── Accounts.txt
├── Books.txt
├── Checklists.txt
├── Shopping.txt
├── standardnotes-fs.txt
├── Todo.txt
└── Wifi.txt
5 directories, 13 files

$ cat notes/Todo.txt
V Get groceries
V Laundry
X Replace kitchen light
O Write standardnotes-fs readme
O Release standardnotes-fs

# Editing:
$ vim notes/Shopping.txt
$ vim notes/tags/lists/Todo.txt

# Tags:
$ mv notes/Checklists.txt notes/tags/lists/
$ rm notes/tags/projects/standardnotes-fs.txt

$ rsync -Wa notes/ notes_backup/
```

### When finished

Unmount the directory:
```text
$ snfs -u notes/
```

Logout to switch accounts:
```text
$ snfs --logout
```

## Usage
```text
usage: snfs [-h] [--username USERNAME] [--password PASSWORD]
            [-v] [--foreground] [--sync-sec SYNC_SEC]
            [--sync-url SYNC_URL] [--ext EXT]
            [--no-config-files] [--config CONFIG]
            [--creds CREDS] [--allow-other] [--logout] [-u]
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
  --ext EXT            file extension to add to note titles. Default: .txt
  --no-config-files    don't load or create config / cred files
  --config CONFIG      specify a config file location. Defaults to:
                       /home/tanner/.config/standardnotes-fs/standardnotes-fs.conf
  --creds CREDS        specify a credentials file location. Defaults to:
                       /home/tanner/.cache/standardnotes-fs/standardnotes-fs.conf
  --allow-other        allow other system users access
  --logout             remove config files and user credentials
  -u, --unmount        unmount [mountpoint] folder

```

## Installation
### For Debian/Ubuntu based systems

Install dependencies:
```text
$ sudo apt install fuse python3 python3-pip
```

#### With Sudo

Install standardnotes-fs and login:
```text
$ sudo pip3 install --upgrade git+https://github.com/tannercollin/standardnotes-fs
$ snfs ~/notes
Please enter your Standard Notes username: tanner@example.com
Please enter your password (hidden): 
```

#### Without Sudo

Install standardnotes-fs and login:
```text
$ pip3 install --user --upgrade git+https://github.com/tannercollin/standardnotes-fs
$ python3 -m snfs ~/notes
Please enter your Standard Notes username: tanner@example.com
Please enter your password (hidden): 
```

Note: if you don't want to use the `python -m` prefix, you'll need to add python's local bin directory to your `$PATH`.

### For OS X systems

Install dependencies:

https://osxfuse.github.io/
```text
$ brew install python3
```

Install standardnotes-fs and login:
```text
$ pip3 install --upgrade git+https://github.com/tannercollin/standardnotes-fs
$ snfs ~/notes
Please enter your Standard Notes username: tanner@example.com
Please enter your password (hidden): 
```

## Notes
* Important: standardnotes-fs has not been tested vigorously yet. Before you use it, please make a backup of your notes by selecting `Account > Download Data Archive` in the official Standard Notes client.
* Your account password is not stored and the Python variable is deleted after your encryption keys are generated with it.
* Your account's encryption keys are stored in a config file on disk. This can be disabled with `--no-config-file`.
* By default the client syncs with the Standard Notes server every 30 seconds and after any note modifications are saved.
* If connection to the server is lost, it will keep trying to sync periodically.
* Creating hidden files (names beginning with a period) is disabled to prevent junk file creation.
* Notes with identical names are deduplicated by adding a number to the end.
* On the filesystem, notes will have the '.txt' extension appended to their name. Change this with the `--ext` argument. Example: `--ext '.md'`.
* neovim/nvim users have had errors about nvim being "unable to create backup file" when writing. This is a bug with neovim. Executing `mkdir ~/.local/share/nvim/backup` might fix it.

## Development

Install dependencies:
```text
$ sudo apt install fuse python3 python3-pip python-virtualenv python3-virtualenv
$ sudo python3 -m pip install --upgrade setuptools
```

Clone repo, create a venv, activate it, and install:
```text
$ git clone https://github.com/tannercollin/standardnotes-fs.git
$ cd standardnotes-fs
$ virtualenv -p python3 env
$ . env/bin/activate
(env) $ pip install --upgrade --no-cache-dir .
```

Standardnotes-fs is now installed in the virtual environment. Run it:
```text
(env) $ mkdir test
(env) $ snfs -vv --no-config-file --username standardnotes-fs@domain.com --password testaccount test/
```

Exit with ctrl-c or unmount as instructed above.

To make changes, edit the files and re-install it with pip:
```text
(env) $ vim standardnotes_fs/standardnotes_fs.py
(env) $ pip install --upgrade .
```

It's now ready to be ran again with your changes.

## License
This program is free and open-source software licensed under the GNU GPLv3. Please see the `LICENSE` file for details.

That means you have the right to study, change, and distribute the software and source code to anyone and for any purpose as long as you grant the same rights when distributing it. You deserve these rights. Please take advantage of them because I like pull requests and would love to see this code put to use.

## Acknowledgements
Thanks to all the devs behind Standard Notes, Udia, Python, libfuse and FUSE.
