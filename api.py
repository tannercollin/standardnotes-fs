import hashlib, hmac, json, requests, time
from base64 import b64encode, b64decode
from binascii import hexlify, unhexlify
from Crypto.Cipher import AES


class RESTAPI:
    def __init__(self, base_url):
        self.base_url = base_url
        self.headers = {}

    def get(self, route, params=None):
        url = self.base_url + route
        return requests.get(url, params, headers=self.headers).json()

    def post(self, route, data=None):
        url = self.base_url + route
        return requests.post(url, data, headers=self.headers).json()

    def addHeader(self, header):
        self.headers.update(header)

class EncryptionHelper:
    def pure_generatePasswordAndKey(self, password, pw_salt, pw_cost):
        output = hashlib.pbkdf2_hmac('sha512', password.encode(), pw_salt.encode(), pw_cost, dklen=96)
        output = hexlify(output).decode()

        output_length = len(output)
        split_length = output_length // 3
        pw = output[0 : split_length]
        mk = output[split_length : split_length * 2]
        ak = output[split_length * 2 : split_length * 3]
        return {'pw': pw, 'mk': mk, 'ak': ak}

    def pure_decryptResponseItems(self, response_items, keys):
        return [self.pure_decryptItem(item, keys) for item in response_items]

    def pure_decryptItem(self, item, keys):
        uuid = item['uuid']
        content = item['content']
        enc_item_key = item['enc_item_key']

        if not content:
            return item

        if content[:3] == '002':
            item_key = self.pure_decryptString002(enc_item_key, keys['mk'], keys['ak'], uuid)
            item_key_length = len(item_key)
            item_ek = item_key[:item_key_length//2]
            item_ak = item_key[item_key_length//2:]

            dec_content = self.pure_decryptString002(content, item_ek, item_ak, uuid)
        else:
            print('Invalid protocol version.')

        dec_item = item
        dec_item['content'] = json.loads(dec_content)
        return dec_item

    def pure_decryptString002(self, string_to_decrypt, encryption_key, auth_key, uuid):
        components = string_to_decrypt.split(':')
        version = components[0]
        auth_hash = components[1]
        local_uuid = components[2]
        IV = components[3]
        ciphertext = components[4]

        if local_uuid != uuid:
            print('UUID does not match.')
            return

        string_to_auth = ':'.join([version, uuid, IV, ciphertext])
        local_auth_hash = hmac.new(unhexlify(auth_key), string_to_auth.encode(), 'sha256').digest()
        local_auth_hash = hexlify(local_auth_hash).decode()

        if local_auth_hash != auth_hash:
            print('Message has been tampered with.')
            return

        cipher = AES.new(unhexlify(encryption_key), AES.MODE_CBC, unhexlify(IV))
        result = cipher.decrypt(b64decode(ciphertext))
        result = result[:-result[-1]] # remove PKCS#7 padding

        return result.decode()

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
        for key, value in self.items.items():
            if value['content_type'] == 'Note':
                note = value['content']
                notes[note['title']] = note['text'] + '\n'
        return notes

class StandardNotesAPI:
    encryption_helper = EncryptionHelper()
    item_manager = ItemManager()
    base_url = 'https://sync.standardnotes.org'
    sync_token = None

    def getAuthParamsForEmail(self):
        return self.api.get('/auth/params', {'email': self.username})

    def signIn(self, password):
        pw_info = self.getAuthParamsForEmail()
        self.keys = self.encryption_helper.pure_generatePasswordAndKey(password, pw_info['pw_salt'], pw_info['pw_cost'])
        res = self.api.post('/auth/sign_in', {'email': self.username, 'password': self.keys['pw']})
        self.api.addHeader({'Authorization': 'Bearer ' + res['token']})

    def refreshItems(self):
        res = self.api.post('/items/sync', {'sync_token': self.sync_token})
        print(json.dumps(res))
        self.sync_token = res['sync_token']
        self.handleResponseItems(res['retrieved_items'])

    def handleResponseItems(self, response_items):
        decrypted_items = self.encryption_helper.pure_decryptResponseItems(response_items, self.keys)
        self.item_manager.mapResponseItemsToLocalItems(decrypted_items)

    def getNotes(self):
        self.refreshItems()
        return self.item_manager.getNotes()

    def __init__(self, username, password):
        self.api = RESTAPI(self.base_url)
        self.username = username
        self.signIn(password)

if __name__ == "__main__":
    notes = StandardNotesAPI('tanner@domain.com', 'complexpass')

    while True:
        notes.refreshItems()
        print(notes.getNotes())

        time.sleep(1)
