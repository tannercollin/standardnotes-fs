from __future__ import print_function, absolute_import, division

import errno
import iso8601
import logging
import os

from stat import S_IFDIR, S_IFREG
from sys import argv, exit
from datetime import datetime
from pathlib import PurePath

from fuse import FUSE, FuseOSError, Operations, LoggingMixIn
from itemmanager import ItemManager

class StandardNotesFUSE(LoggingMixIn, Operations):
    def __init__(self, sn_api, path='.'):
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

    def _pathToNote(self, path):
        pp = PurePath(path)
        note_name = pp.parts[1]
        note = self.notes[note_name]
        return note, note['uuid']

    def getattr(self, path, fh=None):
        self.notes = self.item_manager.getNotes()

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
        return note['text'][offset : offset + size].encode()

    def truncate(self, path, length, fh=None):
        note, uuid = self._pathToNote(path)
        text = note['text'][:length]

        self.item_manager.writeNote(uuid, text)

    def write(self, path, data, offset, fh):
        note, uuid = self._pathToNote(path)

        try:
            text = note['text'][:offset] + data.decode()
        except UnicodeError:
            logging.error('Unable to parse non-unicode data.')
            raise FuseOSError(errno.EIO)

        self.item_manager.writeNote(uuid, text)

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
        return 0

    def unlink(self, path):
        note, uuid = self._pathToNote(path)

        self.item_manager.deleteNote(uuid)
        return 0

    def mkdir(self, path, mode):
        logging.error('Creation of directories is disabled.')
        raise FuseOSError(errno.EPERM)

    def utimens(self, path, times=None):
        note, uuid = self._pathToNote(path)

        self.item_manager.touchNote(uuid)
        return 0

    def chmod(self, path, mode):
        return 0

    def chown(self, path, uid, gid):
        return 0

    def destroy(self, path):
        return 0

    def readlink(self, path):
        return 0

    def rename(self, old, new):
        return 0

    def rmdir(self, path):
        return 0

    def symlink(self, target, source):
        return 0
