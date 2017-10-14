import errno
import iso8601
import logging
import os
import time

from stat import S_IFDIR, S_IFREG
from sys import argv, exit
from datetime import datetime
from pathlib import PurePath
from threading import Thread, Event

from fuse import FUSE, FuseOSError, Operations, LoggingMixIn
from itemmanager import ItemManager
from requests.exceptions import ConnectionError

class StandardNotesFUSE(LoggingMixIn, Operations):
    def __init__(self, sn_api, sync_sec, path='.'):
        self.item_manager = ItemManager(sn_api)
        self.notes = self.item_manager.getNotes()

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
        self.sync_thread = Thread(target=self._syncThread)

    def init(self, path):
        self.sync_thread.start()

    def destroy(self, path):
        self._syncNow()
        logging.info('Stopping sync thread.')
        self.stop_sync.set()
        self.sync_thread.join()
        return 0

    def _syncThread(self):
        while not self.stop_sync.is_set():
            self.run_sync.clear()
            manually_synced = self.run_sync.wait(timeout=self.sync_sec)
            if not manually_synced: logging.info('Auto-syncing items...')
            time.sleep(0.1) # fixes race condition of quick create() then write()
            try:
                self.item_manager.syncItems()
            except ConnectionError:
                logging.error('Unable to connect to sync server. Retrying...')

    def _syncNow(self):
        self.run_sync.set()

    def _pathToNote(self, path):
        pp = PurePath(path)
        note_name = pp.parts[1]
        self.notes = self.item_manager.getNotes()
        note = self.notes[note_name]
        return note, note['uuid']

    def getattr(self, path, fh=None):
        if path == '/':
            return self.dir_stat

        try:
            note, uuid = self._pathToNote(path)
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
        note, uuid = self._pathToNote(path)
        return note['text'][offset : offset + size]

    def truncate(self, path, length, fh=None):
        note, uuid = self._pathToNote(path)
        text = note['text'][:length]
        self.item_manager.writeNote(uuid, text)
        self._syncNow()
        return 0

    def write(self, path, data, offset, fh):
        note, uuid = self._pathToNote(path)
        text = note['text'][:offset] + data

        try:
            self.item_manager.writeNote(uuid, text)
        except UnicodeError:
            logging.error('Unable to parse non-unicode data.')
            raise FuseOSError(errno.EIO)

        self._syncNow()
        return len(data)

    def create(self, path, mode):
        path_parts = path.split('/')
        note_name = path_parts[1]

        # disallow hidden files (usually editor / OS files)
        if note_name[0] == '.':
            logging.error('Creation of hidden files is disabled.')
            raise FuseOSError(errno.EPERM)

        now = datetime.utcnow().isoformat()[:-3] + 'Z' # hack

        self.item_manager.createNote(note_name, now)
        self._syncNow()
        return 0

    def unlink(self, path):
        note, uuid = self._pathToNote(path)
        self.item_manager.deleteNote(uuid)
        self._syncNow()
        return 0

    def mkdir(self, path, mode):
        logging.error('Creation of directories is disabled.')
        raise FuseOSError(errno.EPERM)

    def utimens(self, path, times=None):
        note, uuid = self._pathToNote(path)
        self.item_manager.touchNote(uuid)
        self._syncNow()
        return 0

    def rename(self, old, new):
        note, uuid = self._pathToNote(old)
        new_path_parts = new.split('/')
        new_note_name = new_path_parts[1]
        self.item_manager.renameNote(uuid, new_note_name)
        self._syncNow()
        return 0

    def chmod(self, path, mode):
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
