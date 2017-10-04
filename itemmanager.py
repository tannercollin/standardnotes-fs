from api import StandardNotesAPI

class ItemManager:
    items = {}

    def mapResponseItemsToLocalItems(self, response_items):
        for response_item in response_items:
            uuid = response_item['uuid']

            if response_item['deleted']:
                if uuid in self.items:
                    del self.items[uuid]
                continue

            self.items[uuid] = response_item

    def getNotes(self):
        notes = {}
        sorted_items = sorted(self.items.items(), key=lambda x: x[1]['created_at'])

        for uuid, item in sorted_items:
            if item['content_type'] == 'Note':
                note = item['content']
                text = note['text'] + '\n'
                count = 0 # used to remove title duplicates

                while True:
                    title = note['title'] + ('' if not count else ' ' + str(count + 1))
                    if title in notes:
                        count += 1
                    else:
                        break

                notes[title] = dict(text=text,
                        created=item['created_at'],
                        modified=item['updated_at'],
                        uuid=item['uuid'])
        return notes

    def __init__(self, username, password):
        self.standard_notes = StandardNotesAPI(username, password)
        response_items = self.standard_notes.sync(None)
        self.mapResponseItemsToLocalItems(response_items)
