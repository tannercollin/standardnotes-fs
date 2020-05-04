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

from standardnotes_fs.itemmanager import ItemManager

DIR_PERMISSIONS = 0o750
FILE_PERMISSIONS = 0o640
ROOT_INODE = 0
TAGS_INODE = 1
TRASH_INODE = 2
ARCHIVED_INODE = 3
INODE_OFFSET = 100

class StandardNotesFUSE(LoggingMixIn, Operations):
    def __init__(self, sn_api, sync_sec, ext, path='.'):
        self.item_manager = ItemManager(sn_api, ext)

        self.uid = os.getuid()
        self.gid = os.getgid()

        now = datetime.now().timestamp()
        self.dir_stat = dict(st_mode=(S_IFDIR | DIR_PERMISSIONS), st_ctime=now,
                             st_mtime=now, st_atime=now, st_nlink=2,
                             st_uid=self.uid, st_gid=self.gid)

        self.note_stat = dict(st_mode=(S_IFREG | FILE_PERMISSIONS), st_ctime=now,
                              st_mtime=now, st_atime=now, st_nlink=1,
                              st_uid=self.uid, st_gid=self.gid)

        self.sync_sec = sync_sec
        self.ext = ext
        self.run_sync = Event()
        self.stop_sync = Event()
        self.sync_thread = Thread(target=self._sync_thread)

    def init(self, path):
        self.sync_thread.start()

    def destroy(self, path):
        self.run_sync.set()
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
                logging.error('Unable to connect to sync server.')

    def _modify_sync(self):
        self.run_sync.set()

    def _path_to_tag(self, path):
        pp = PurePath(path)
        if pp.parts[1] == 'tags':
            tag_name = pp.parts[2]
            tag = self.item_manager.get_tag(tag_name)
            return tag, tag_name, tag['uuid']
        else:
            raise KeyError

    def _path_to_note(self, path):
        pp = PurePath(path)
        note_name = pp.name
        note = self.item_manager.get_note(note_name)
        return note, note_name, note['uuid']

    def note_attr(self, path):
        note, note_name, uuid = self._path_to_note(path)
        st = self.note_stat
        st['st_size'] = len(note['text'])
        st['st_ino'] = note['inode'] + INODE_OFFSET
        st['st_ctime'] = iso8601.parse_date(note['created']).timestamp()
        st['st_mtime'] = iso8601.parse_date(note['modified']).timestamp()
        return st

    def getattr(self, path, fh=None):
        pp = PurePath(path)

        try:
            if path == '/':
                notes = self.item_manager.get_notes()
                st = dict(self.dir_stat, st_ino=ROOT_INODE, st_size=len(notes))
            elif pp.parts[1] == 'tags':
                if len(pp.parts) == 3:
                    tag, tag_name, uuid = self._path_to_tag(path)
                    st = self.dir_stat
                    st['st_size'] = len(tag['notes'])
                    st['st_ino'] = tag['inode'] + INODE_OFFSET
                    st['st_ctime'] = iso8601.parse_date(tag['created']).timestamp()
                    st['st_mtime'] = iso8601.parse_date(tag['modified']).timestamp()
                elif len(pp.parts) == 4:
                    tag, tag_name, tag_uuid = self._path_to_tag(path)
                    note, note_name, note_uuid = self._path_to_note(path)
                    if note_uuid in tag['notes']:
                        st = self.getattr('/' + pp.name) # recursion
                    else:
                        raise KeyError
                else:
                    tags = self.item_manager.get_tags()
                    st = dict(self.dir_stat, st_ino=TAGS_INODE, st_size=len(tags))
            elif pp.parts[1] == 'archived':
                notes = self.item_manager.get_notes(archived=True)

                if len(pp.parts) == 3:
                    if pp.name not in notes: raise KeyError
                    st = self.note_attr(path)
                else:
                    st = dict(self.dir_stat, st_ino=ARCHIVED_INODE, st_size=len(notes))
            elif pp.parts[1] == 'trash':
                notes = self.item_manager.get_notes(trashed=True)

                if len(pp.parts) == 3:
                    if pp.name not in notes: raise KeyError
                    st = self.note_attr(path)
                else:
                    st = dict(self.dir_stat, st_ino=TRASH_INODE, st_size=len(notes))
            else:
                notes = self.item_manager.get_notes()
                if pp.name not in notes: raise KeyError
                st = self.note_attr(path)
        except KeyError:
            raise FuseOSError(errno.ENOENT)

        return st

    def access(self, path, mode):
        if mode == os.X_OK:
            if self.getattr(path)['st_mode'] & S_IFREG:
                raise FuseOSError(errno.EPERM)
            else:
                return 0

        return 0

    def readdir(self, path, fh):
        dirents = ['.', '..']
        pp = PurePath(path)

        if path == '/':
            dirents.extend(self.item_manager.get_notes())
            tags = self.item_manager.get_tags()
            if len(tags): dirents.append('tags')
            archived = self.item_manager.get_notes(archived=True)
            if archived: dirents.append('archived')
            trashed = self.item_manager.get_notes(trashed=True)
            if trashed: dirents.append('trash')
        elif pp.parts[1] == 'tags':
            if len(pp.parts) == 3:
                tag, tag_name, uuid = self._path_to_tag(path)
                notes = [note for note in self.item_manager.get_notes()
                    if self.item_manager.get_note_uuid(note) in tag['notes']]
                dirents.extend(notes)
            else:
                tags = self.item_manager.get_tags()
                dirents.extend(list(tags.keys()))
        elif pp.parts[1] == 'archived':
            archived = self.item_manager.get_notes(archived=True)
            dirents.extend(archived)
        elif pp.parts[1] == 'trash':
            trashed = self.item_manager.get_notes(trashed=True)
            dirents.extend(trashed)

        return dirents

    def read(self, path, size, offset, fh):
        note, note_name, uuid = self._path_to_note(path)
        return note['text'][offset : offset + size]

    def truncate(self, path, length, fh=None):
        note, note_name, uuid = self._path_to_note(path)
        text = note['text'][:length]
        self.item_manager.write_note(uuid, text)
        self._modify_sync()
        return 0

    def write(self, path, data, offset, fh):
        note, note_name, uuid = self._path_to_note(path)
        text = note['text'][:offset] + data

        try:
            self.item_manager.write_note(uuid, text)
        except UnicodeError:
            logging.error('Unable to parse non-unicode data.')
            raise FuseOSError(errno.EIO)

        self._modify_sync()
        return len(data)

    def create(self, path, mode):
        pp = PurePath(path)
        note_name = pp.name

        # disallow created notes in these directories
        if len(pp.parts) < 4 and pp.parts[1] in ['tags', 'archived', 'trash']:
            logging.error('Unable to create files in that directory.')
            raise FuseOSError(errno.EPERM)

        # disallow hidden files (usually editor / OS files)
        if note_name[0] == '.':
            logging.error('Creation of hidden files is disabled.')
            raise FuseOSError(errno.EPERM)

        # makes sure writing / stat operations are consistent
        if pp.suffix != self.ext:
            logging.error('New notes must end in ' + self.ext)
            raise FuseOSError(errno.EPERM)

        if note_name in self.item_manager.get_all_notes():
            logging.error('Note already exists.')
            raise FuseOSError(errno.EPERM)

        title = pp.stem

        note_uuid = self.item_manager.create_note(title)

        if pp.parts[1] == 'tags':
            tag, tag_name, tag_uuid = self._path_to_tag(path)
            self.item_manager.tag_note(tag_uuid, note_uuid)

        self._modify_sync()
        return 0

    def unlink(self, path):
        pp = PurePath(path)

        if pp.parts[1] == 'tags':
            tag, tag_name, tag_uuid = self._path_to_tag(path)
            note, note_name, note_uuid = self._path_to_note(path)
            self.item_manager.untag_note(tag_uuid, note_uuid)
            self._modify_sync()
            return 0
        else:
            note, note_name, uuid = self._path_to_note(path)
            self.item_manager.delete_note(uuid)
            self._modify_sync()
            return 0

    def mkdir(self, path, mode):
        pp = PurePath(path)

        if pp.parts[1] == 'tags' and len(pp.parts) == 3:
            self.item_manager.create_tag(pp.parts[2])
            self._modify_sync()
            return 0

        raise FuseOSError(errno.EPERM)

    def utimens(self, path, times=None):
        pp = PurePath(path)

        if pp.parts[1] == 'tags':
            logging.error('Touching tags not yet supported.')
            raise FuseOSError(errno.EPERM)

        note, note_name, uuid = self._path_to_note(path)
        self.item_manager.touch_note(uuid)
        self._modify_sync()
        return 0

    def rename(self, old, new):
        pp_old = PurePath(old)
        pp_new = PurePath(new)

        # rename, archive, trash note
        if pp_old.parts[1] != 'tags' and pp_new.parts[1] != 'tags':
            note, note_name, uuid = self._path_to_note(old)
            self.item_manager.rename_note(uuid, pp_new)
            self._modify_sync()
            return 0

        # rename tag
        if (len(pp_old.parts) == 3 and len(pp_new.parts) == 3
            and pp_old.parts[1] == 'tags' and pp_new.parts[1] == 'tags'):
            tag, tag_name, tag_uuid = self._path_to_tag(old)
            self.item_manager.rename_tag(tag_uuid, pp_new.name)
            self._modify_sync()
            return 0

        if pp_old.parts[-1] != pp_new.parts[-1]:
            logging.error('Unable to rename note from inside tags folder.')
            raise FuseOSError(errno.EPERM)

        # tag note
        if pp_new.parts[1] == 'tags' and len(pp_new.parts) == 4:
            tag, tag_name, tag_uuid = self._path_to_tag(new)
            note, note_name, note_uuid = self._path_to_note(old)
            self.item_manager.tag_note(tag_uuid, note_uuid)
        else:
            logging.error('Invalid mv operation.')
            raise FuseOSError(errno.EPERM)

        self._modify_sync()
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
        pp = PurePath(path)

        if pp.parts[1] == 'tags' and len(pp.parts) == 3:
            tag, tag_name, uuid = self._path_to_tag(path)
            self.item_manager.delete_tag(uuid)
            self._modify_sync()
            return 0

        raise FuseOSError(errno.EPERM)

    def symlink(self, target, source):
        return 0
