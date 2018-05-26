from datetime import datetime
import errno
import logging
import os
from pathlib import PurePath
from stat import S_IFDIR, S_IFREG
from threading import Event, Thread
from time import sleep

from fuse import FuseOSError, LoggingMixIn, Operations
import iso8601
from requests.exceptions import ConnectionError

from itemmanager import ItemManager

class StandardNotesFUSE(LoggingMixIn, Operations):
    def __init__(self, sn_api, sync_sec, path='.'):
        self.item_manager = ItemManager(sn_api)
        self.notes = self.item_manager.get_notes()

        self.uid = os.getuid()
        self.gid = os.getgid()

        now = datetime.now().timestamp()
        self.dir_stat = dict(st_mode=(S_IFDIR | 0o755), st_ctime=now,
                             st_mtime=now, st_atime=now, st_nlink=2,
                             st_uid=self.uid, st_gid=self.gid)

        self.note_stat = dict(st_mode=(S_IFREG | 0o644), st_ctime=now,
                              st_mtime=now, st_atime=now, st_nlink=1,
                              st_uid=self.uid, st_gid=self.gid)

        self.sync_sec = sync_sec
        self.run_sync = Event()
        self.stop_sync = Event()
        self.sync_thread = Thread(target=self._sync_thread)

    def init(self, path):
        self.sync_thread.start()

    def destroy(self, path):
        self._sync_now()
        logging.info('Stopping sync thread.')
        self.stop_sync.set()
        self.sync_thread.join()
        return 0

    def _sync_thread(self):
        while not self.stop_sync.is_set():
            self.run_sync.clear()
            manually_synced = self.run_sync.wait(timeout=self.sync_sec)
            if not manually_synced: logging.info('Auto-syncing items...')
            sleep(0.1) # fixes race condition of quick create() then write()
            try:
                self.item_manager.sync_items()
            except ConnectionError:
                logging.error('Unable to connect to sync server. Retrying...')

    def _sync_now(self):
        self.run_sync.set()

    def _path_to_note(self, path):
        pp = PurePath(path)
        note_name = pp.parts[1]
        self.notes = self.item_manager.get_notes()
        note = self.notes[note_name]
        return note, note['uuid']

    def getattr(self, path, fh=None):
        if path == '/':
            return self.dir_stat

        try:
            note, uuid = self._path_to_note(path)
            st = self.note_stat
            st['st_size'] = len(note['text'])
            st['st_ctime'] = iso8601.parse_date(note['created']).timestamp()
            st['st_mtime'] = iso8601.parse_date(note['modified']).timestamp()
            return st
        except KeyError:
            raise FuseOSError(errno.ENOENT)

    def readdir(self, path, fh):
        dirents = ['.', '..']

        if path == '/':
            dirents.extend(list(self.notes.keys()))
        return dirents

    def read(self, path, size, offset, fh):
        note, uuid = self._path_to_note(path)
        return note['text'][offset : offset + size]

    def truncate(self, path, length, fh=None):
        note, uuid = self._path_to_note(path)
        text = note['text'][:length]
        self.item_manager.write_note(uuid, text)
        self._sync_now()
        return 0

    def write(self, path, data, offset, fh):
        note, uuid = self._path_to_note(path)
        text = note['text'][:offset] + data

        try:
            self.item_manager.write_note(uuid, text)
        except UnicodeError:
            logging.error('Unable to parse non-unicode data.')
            raise FuseOSError(errno.EIO)

        self._sync_now()
        return len(data)

    def create(self, path, mode):
        path_parts = path.split('/')
        note_name = path_parts[1]

        # disallow hidden files (usually editor / OS files)
        if note_name[0] == '.':
            logging.error('Creation of hidden files is disabled.')
            raise FuseOSError(errno.EPERM)

        if note_name.endswith('.txt'):
            note_name = note_name[:-4]

        now = datetime.utcnow().isoformat()[:-3] + 'Z' # hack

        self.item_manager.create_note(note_name, now)
        self._sync_now()
        return 0

    def unlink(self, path):
        note, uuid = self._path_to_note(path)
        self.item_manager.delete_note(uuid)
        self._sync_now()
        return 0

    def mkdir(self, path, mode):
        logging.error('Creation of directories is disabled.')
        raise FuseOSError(errno.EPERM)

    def utimens(self, path, times=None):
        note, uuid = self._path_to_note(path)
        self.item_manager.touch_note(uuid)
        self._sync_now()
        return 0

    def rename(self, old, new):
        note, uuid = self._path_to_note(old)
        new_path_parts = new.split('/')
        new_note_name = new_path_parts[1]
        self.item_manager.rename_note(uuid, new_note_name)
        self._sync_now()
        return 0

    def chmod(self, path, mode):
        if mode == self.note_stat['st_mode']:
            return 0
        else:
            logging.error('chmod is disabled.')
            raise FuseOSError(errno.EPERM)

    def chown(self, path, uid, gid):
        logging.error('chown is disabled.')
        raise FuseOSError(errno.EPERM)

    def readlink(self, path):
        return 0

    def rmdir(self, path):
        return 0

    def symlink(self, target, source):
        return 0
