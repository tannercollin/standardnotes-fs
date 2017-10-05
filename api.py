import hashlib, hmac, json, requests, time
from base64 import b64encode, b64decode
from binascii import hexlify, unhexlify
from Crypto.Cipher import AES
from Crypto.Random import random
from copy import deepcopy


class RESTAPI:
    def __init__(self, base_url):
        self.base_url = base_url
        self.headers = {}

    def get(self, route, params=None):
        url = self.base_url + route
        return requests.get(url, params, headers=self.headers).json()

    def post(self, route, data=None):
        url = self.base_url + route
        print(data)
        res = requests.post(url, json=data, headers=self.headers)
        print(res.text)
        return res.json()

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
        return dict(pw=pw, mk=mk, ak=ak)

    def encryptDirtyItems(self, dirty_items, keys):
        return [self.pure_encryptItem(item, keys) for item in dirty_items]

    def decryptResponseItems(self, response_items, keys):
        return [self.pure_decryptItem(item, keys) for item in response_items]

    def pure_encryptItem(self, item, keys):
        uuid = item['uuid']
        content = json.dumps(item['content'])

        item_key = hex(random.getrandbits(512))
        item_key = item_key[2:].rjust(128, '0') # remove '0x', pad to 128
        item_key_length = len(item_key)
        item_ek = item_key[:item_key_length//2]
        item_ak = item_key[item_key_length//2:]

        enc_item = deepcopy(item)
        enc_item['content'] = self.pure_encryptString002(content, item_ek, item_ak, uuid)
        enc_item['enc_item_key'] = self.pure_encryptString002(item_key, keys['mk'], keys['ak'], uuid)
        return enc_item

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

        dec_item = deepcopy(item)
        dec_item['content'] = json.loads(dec_content)
        return dec_item

    def pure_encryptString002(self, string_to_encrypt, encryption_key, auth_key, uuid):
        IV = hex(random.getrandbits(128))
        IV = IV[2:].rjust(32, '0') # remove '0x', pad to 32

        cipher = AES.new(unhexlify(encryption_key), AES.MODE_CBC, unhexlify(IV))
        pt = string_to_encrypt.encode()
        pad = 16 - len(pt) % 16
        padded_pt = pt + pad * bytes([pad])
        ciphertext = b64encode(cipher.encrypt(padded_pt)).decode()

        string_to_auth = ':'.join(['002', uuid, IV, ciphertext])
        auth_hash = hmac.new(unhexlify(auth_key), string_to_auth.encode(), 'sha256').digest()
        auth_hash = hexlify(auth_hash).decode()

        result = ':'.join(['002', auth_hash, uuid, IV, ciphertext])

        return result

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

class StandardNotesAPI:
    encryption_helper = EncryptionHelper()
    base_url = 'https://sync.standardnotes.org'
    sync_token = None

    def getAuthParamsForEmail(self):
        return self.api.get('/auth/params', dict(email=self.username))

    def signIn(self, password):
        pw_info = self.getAuthParamsForEmail()
        self.keys = self.encryption_helper.pure_generatePasswordAndKey(password, pw_info['pw_salt'], pw_info['pw_cost'])
        res = self.api.post('/auth/sign_in', dict(email=self.username, password=self.keys['pw']))
        self.api.addHeader(dict(Authorization='Bearer ' + res['token']))

    def sync(self, dirty_items):
        items = self.handleDirtyItems(dirty_items)
        if items:
            json_items = items
            print(json_items)
        else:
            json_items = []
        response = self.api.post('/items/sync', dict(sync_token=self.sync_token, items=json_items))
        print(json.dumps(response))

        self.sync_token = response['sync_token']
        return self.handleResponseItems(response)

    def handleDirtyItems(self, dirty_items):
        items = self.encryption_helper.encryptDirtyItems(dirty_items, self.keys)
        return items

    def handleResponseItems(self, response):
        response_items = self.encryption_helper.decryptResponseItems(response['retrieved_items'], self.keys)
        saved_items = self.encryption_helper.decryptResponseItems(response['saved_items'], self.keys)
        return dict(response_items=response_items, saved_items=saved_items)

    def __init__(self, username, password):
        self.api = RESTAPI(self.base_url)
        self.username = username
        self.signIn(password)

if __name__ == '__main__':
        standard_notes = StandardNotesAPI('tanner@domain.com', 'complexpass')
        test_item = standard_notes.encryption_helper.pure_encryptItem(dict(content=dict(hello='world'), uuid='1234'), standard_notes.keys)
        print(test_item)
        test_item = standard_notes.encryption_helper.pure_decryptItem(test_item, standard_notes.keys)
        print(test_item)
