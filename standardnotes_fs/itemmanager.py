from uuid import uuid1

from standardnotes_fs.api import StandardNotesAPI

class ItemManager:
    items = {}

    def map_items(self, response_items, metadata_only=False):
        DATA_KEYS = ['content', 'enc_item_key', 'auth_hash']

        for response_item in response_items:
            uuid = response_item['uuid']

            if response_item['deleted']:
                if uuid in self.items:
                    del self.items[uuid]
                continue

            response_item['dirty'] = False

            if uuid not in self.items:
                self.items[uuid] = {}

            for key, value in response_item.items():
                if metadata_only and key in DATA_KEYS:
                    continue
                self.items[uuid][key] = value

    def sync_items(self):
        dirty_items = [item for uuid, item in self.items.items() if item['dirty']]

        # remove keys (note: this removes them from self.items as well)
        for item in dirty_items:
            item.pop('dirty', None)
            item.pop('updated_at', None)

        response = self.sn_api.sync(dirty_items)
        self.map_items(response['response_items'])
        self.map_items(response['saved_items'], metadata_only=True)

    def get_notes(self):
        notes = {}
        note_items = [item for uuid, item in self.items.items()
                if item['content_type'] == 'Note']
        sorted_note_items = sorted(note_items, key=lambda x: x['created_at'])

        for item in sorted_note_items:
            note = item['content']
            text = note['text']

            # Add a new line so it outputs pretty
            if not text.endswith('\n'):
                text += '\n';

            text = text.encode() # convert to binary data

            # remove title duplicates by adding a number to the end
            count = 0
            while True:
                title = note['title'] + ('' if not count else str(count + 1))

                # clean up filenames
                title = title.replace('/', '-').replace(' ', '_') + '.txt'

                if title in notes:
                    count += 1
                else:
                    break

            notes[title] = dict(note_name=title, text=text, uuid=item['uuid'],
                    created=item['created_at'],
                    modified=item.get('updated_at', item['created_at']))
        return notes

    def touch_note(self, uuid):
        item = self.items[uuid]
        item['dirty'] = True

    def write_note(self, uuid, text):
        item = self.items[uuid]
        item['content']['text'] = text.decode() # convert back to string
        item['dirty'] = True

    def create_note(self, name, time):
        uuid = str(uuid1())
        content = dict(title=name, text='', references=[])
        self.items[uuid] = dict(content_type='Note', dirty=True, auth_hash=None,
                                uuid=uuid, created_at=time, updated_at=time,
                                enc_item_key='', content=content)

    def rename_note(self, uuid, new_note_name):
        item = self.items[uuid]
        item['content']['title'] = new_note_name
        item['dirty'] = True

    def delete_note(self, uuid):
        item = self.items[uuid]
        item['deleted'] = True
        item['dirty'] = True

    def get_tags(self):
        tags = {}
        tag_items = [item for uuid, item in self.items.items()
                if item['content_type'] == 'Tag']
        sorted_tag_items = sorted(tag_items, key=lambda x: x['created_at'])

        for item in sorted_tag_items:
            tag = item['content']
            references = tag['references']

            notes = [r['uuid'] for r in references if r['content_type'] == 'Note']

            # remove title duplicates by adding a number to the end
            count = 0
            while True:
                title = tag['title'] + ('' if not count else str(count + 1))

                # clean up filenames
                title = title.replace('/', '-').replace(' ', '_')

                if title in tags:
                    count += 1
                else:
                    break

            tags[title] = dict(tag_name=title, notes=notes, uuid=item['uuid'],
                    created=item['created_at'],
                    modified=item.get('updated_at', item['created_at']))

        return tags

    def __init__(self, sn_api):
        self.sn_api = sn_api
        self.sync_items()
