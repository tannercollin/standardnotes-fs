from __future__ import print_function, absolute_import, division

import errno
import logging
import os

from stat import S_IFDIR, S_IFREG
from sys import argv, exit
from time import time

from fuse import FUSE, FuseOSError, Operations, LoggingMixIn
from api import StandardNotesAPI


class StandardNotesFS(LoggingMixIn, Operations):
    def __init__(self, path='.'):
        self.standard_notes = StandardNotesAPI('tanner@domain.com', 'complexpass')
        self.notes = self.standard_notes.getNotes()

        self.uid = os.getuid()
        self.gid = os.getgid()

        now = time()
        self.dir_stat = dict(st_mode=(S_IFDIR | 0o755), st_ctime=now,
                            st_mtime=now, st_atime=now, st_nlink=2,
                            st_uid=self.uid, st_gid=self.gid)

        self.note_stat = dict(st_mode=(S_IFREG | 0o644), st_ctime=now,
                            st_mtime=now, st_atime=now, st_nlink=1,
                            st_uid=self.uid, st_gid=self.gid)

    def getattr(self, path, fh=None):
        st = self.note_stat

        path_parts = path.split('/')
        note_name = path_parts[1]

        if path == '/':
            return self.dir_stat
        elif note_name in self.notes:
            st['st_size'] = len(self.notes[note_name])
            return st
        else:
            raise FuseOSError(errno.ENOENT)

    def readdir(self, path, fh):
        dirents = ['.', '..']

        if path == '/':
            dirents.extend(list(self.notes.keys()))
        return dirents

    def read(self, path, size, offset, fh):
        path_parts = path.split('/')
        note_name = path_parts[1]

        return self.notes[note_name][offset : offset + size].encode()

    def chmod(self, path, mode):
        return 0

    def chown(self, path, uid, gid):
        return 0

    def create(self, path, mode):
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

    def unlink(self, path):
        return 0

    def utimens(self, path, times=None):
        return 0

    def write(self, path, data, offset, fh):
        return 0

if __name__ == '__main__':
    if len(argv) != 2:
        print('usage: %s <mountpoint>' % argv[0])
        exit(1)

    logging.basicConfig(level=logging.DEBUG)

    fuse = FUSE(StandardNotesFS(), argv[1], foreground=True, nothreads=True)
