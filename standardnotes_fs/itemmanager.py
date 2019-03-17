from datetime import datetime
from copy import deepcopy
from uuid import uuid1

from standardnotes_fs.api import StandardNotesAPI

class ItemManager:
    items = {}
    note_uuids = {}
    note_titles = {}
    tag_uuids = {}
    tag_titles = {}
    ext = ''

    def cache_item_title(self, item, uuid_cache, title_cache):
        # remove title from caches if it's in there
        uuid_cache.pop(title_cache.pop(item['uuid'], None), None)

        if item['deleted']:
            return

        content = item['content']
        content_type = item['content_type']
        original_title = content.get('title', 'Untitled')

        # remove title duplicates by adding a number to the end
        count = 0
        while True:
            title = original_title + ('' if not count else str(count + 1))

            # clean up filenames
            title = title.replace('/', '-')
            if content_type == 'Note':
                title += self.ext

            if title in uuid_cache:
                count += 1
            else:
                break

        uuid_cache[title] = item['uuid']
        title_cache[item['uuid']] = title

    def map_items(self, response_items, metadata_only=False):
        DATA_KEYS = ['content', 'enc_item_key', 'auth_hash']

        # sort so deduplication is consistent
        response_items = sorted(response_items, key=lambda x: x['created_at'])

        for item in response_items:
            uuid = item['uuid']

            if item['content_type'] == 'Note':
                self.cache_item_title(item, self.note_uuids, self.note_titles)
            elif item['content_type'] == 'Tag':
                self.cache_item_title(item, self.tag_uuids, self.tag_titles)

            if item['deleted']:
                if uuid in self.items:
                    del self.items[uuid]
                continue

            item['dirty'] = False

            if uuid not in self.items:
                self.items[uuid] = {}

            for key, value in item.items():
                if metadata_only and key in DATA_KEYS:
                    continue
                self.items[uuid][key] = value

    def sync_items(self):
        dirty_items = [deepcopy(item) for _, item in self.items.items() if item['dirty']]

        # remove keys
        for item in dirty_items:
            item.pop('dirty', None)
            item.pop('updated_at', None)

        response = self.sn_api.sync(dirty_items)
        self.map_items(response['response_items'])
        self.map_items(response['saved_items'], metadata_only=True)

    def get_updated(self, item):
        try:
            return item['content']['appData']['org.standardnotes.sn']['client_updated_at']
        except KeyError:
            return item.get('updated_at', item['created_at'])

    def get_archived(self, item):
        try:
            return item['content']['appData']['org.standardnotes.sn']['archived']
        except KeyError:
            return False

    def get_trashed(self, item):
        try:
            return item['content']['trashed']
        except KeyError:
            return False

    def get_note(self, title):
        item = self.items[self.note_uuids[title]]
        note = item['content']
        text = note['text']

        # Add a new line so it outputs pretty
        if not text.endswith('\n'):
            text += '\n';

        text = text.encode() # convert to binary data

        return dict(note_name=title, text=text, uuid=item['uuid'],
                created=item['created_at'],
                modified=self.get_updated(item))

    def get_note_uuid(self, title):
        return self.note_uuids[title]

    def get_notes(self, archived=False, trashed=False):
        notes = [(k, self.items[v]) for k, v in self.note_uuids.items()]

        if archived and trashed:
            return []
        elif archived:
            return [k for k, v in notes if self.get_archived(v) and not self.get_trashed(v)]
        elif trashed:
            return [k for k, v in notes if self.get_trashed(v)]
        else:
            return [k for k, v in notes if not (self.get_archived(v) or self.get_trashed(v))]

    def set_dirty(self, item):
        item['dirty'] = True

        ref = item['content']
        ref = ref.setdefault('appData', {})
        ref = ref.setdefault('org.standardnotes.sn', {})
        ref['client_updated_at'] = datetime.utcnow().isoformat() + 'Z'

    def touch_note(self, uuid):
        item = self.items[uuid]
        self.set_dirty(item)

    def write_note(self, uuid, text):
        item = self.items[uuid]
        item['content']['text'] = text.decode() # convert back to string
        self.set_dirty(item)

    def create_note(self, name):
        uuid = str(uuid1())
        content = dict(title=name, text='', references=[])
        creation_time = datetime.utcnow().isoformat() + 'Z'
        self.items[uuid] = dict(content_type='Note', auth_hash=None,
                                uuid=uuid, created_at=creation_time,
                                enc_item_key='', content=content)
        item = self.items[uuid]
        self.set_dirty(item)

    def rename_note(self, uuid, new_note_name):
        item = self.items[uuid]
        item['content']['title'] = new_note_name
        self.set_dirty(item)

    def delete_note(self, uuid):
        item = self.items[uuid]

        if self.get_trashed(item):
            item['deleted'] = True
        else:
            item['content']['trashed'] = True

        self.set_dirty(item)

    def get_tag(self, title):
        item = self.items[self.tag_uuids[title]]
        tag = item['content']
        references = tag['references']
        notes = [r['uuid'] for r in references if r['content_type'] == 'Note']

        return dict(tag_name=title, notes=notes, uuid=item['uuid'],
                created=item['created_at'],
                modified=self.get_updated(item))

    def get_tags(self):
        return self.tag_uuids

    def __init__(self, sn_api, ext):
        self.sn_api = sn_api
        self.ext = ext
        self.sync_items()
