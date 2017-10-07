from __future__ import print_function, absolute_import, division

import errno
import iso8601
import logging
import os

from stat import S_IFDIR, S_IFREG
from sys import argv, exit
from datetime import datetime

from fuse import FUSE, FuseOSError, Operations, LoggingMixIn
from itemmanager import ItemManager

class StandardNotesFS(LoggingMixIn, Operations):
    def __init__(self, path='.'):
        self.item_manager = ItemManager('tanner@domain.com', 'complexpass')

        self.uid = os.getuid()
        self.gid = os.getgid()

        now = datetime.now().timestamp()
        self.dir_stat = dict(st_mode=(S_IFDIR | 0o755), st_ctime=now,
                            st_mtime=now, st_atime=now, st_nlink=2,
                            st_uid=self.uid, st_gid=self.gid)

        self.note_stat = dict(st_mode=(S_IFREG | 0o644), st_ctime=now,
                            st_mtime=now, st_atime=now, st_nlink=1,
                            st_uid=self.uid, st_gid=self.gid)

    def getattr(self, path, fh=None):
        self.notes = self.item_manager.getNotes()

        st = self.note_stat

        path_parts = path.split('/')
        note_name = path_parts[1]

        if path == '/':
            return self.dir_stat
        elif note_name in self.notes:
            note = self.notes[note_name]
            st['st_size'] = len(note['text'])
            st['st_ctime'] = iso8601.parse_date(note['created']).timestamp()
            st['st_mtime'] = iso8601.parse_date(note['modified']).timestamp()
            return st
        else:
            raise FuseOSError(errno.ENOENT)

    def readdir(self, path, fh):
        self.notes = self.item_manager.getNotes()

        dirents = ['.', '..']

        if path == '/':
            dirents.extend(list(self.notes.keys()))
        return dirents

    def read(self, path, size, offset, fh):
        self.notes = self.item_manager.getNotes()

        path_parts = path.split('/')
        note_name = path_parts[1]
        note = self.notes[note_name]

        return note['text'][offset : offset + size].encode()

    def write(self, path, data, offset, fh):
        self.notes = self.item_manager.getNotes()

        path_parts = path.split('/')
        note_name = path_parts[1]
        note = self.notes[note_name]
        text = note['text'][:offset] + data.decode()
        uuid = note['uuid']

        self.item_manager.writeNote(uuid, text)

        return len(data)

    def create(self, path, mode):
        path_parts = path.split('/')
        note_name = path_parts[1]
        now = datetime.utcnow().isoformat()[:-3] + 'Z' # hack

        self.item_manager.createNote(note_name, now)
        return 0

    def unlink(self, path):
        self.notes = self.item_manager.getNotes()

        path_parts = path.split('/')
        note_name = path_parts[1]
        note = self.notes[note_name]
        uuid = note['uuid']

        self.item_manager.deleteNote(uuid)

        return 0

    def chmod(self, path, mode):
        return 0

    def chown(self, path, uid, gid):
        return 0

    def destroy(self, path):
        return 0

    def mkdir(self, path, mode):
        return 0

    def readlink(self, path):
        return 0

    def rename(self, old, new):
        return 0

    def rmdir(self, path):
        return 0

    def symlink(self, target, source):
        return 0

    def truncate(self, path, length, fh=None):
        return 0

    def utimens(self, path, times=None):
        return 0

if __name__ == '__main__':
    if len(argv) != 2:
        print('usage: %s <mountpoint>' % argv[0])
        exit(1)

    logging.basicConfig(level=logging.DEBUG)

    fuse = FUSE(StandardNotesFS(), argv[1], foreground=True, nothreads=True)
