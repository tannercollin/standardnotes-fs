import json
import requests
import sys
import logging

from standardnotes_fs.crypt import EncryptionHelper

API_VERSION = '20200115'
#API_VERSION = '20190520'
ALLOWED_ITEM_TYPES = ['Note', 'Tag']
ALLOWED_ITEM_TYPES_004 = ['Note', 'Tag', 'SN|ItemsKey', 'SN|UserPreferences', 'SN|Component']


class SNAPIException(Exception):
    pass

class RESTAPI:
    def __init__(self, base_url):
        self.base_url = base_url
        self.headers = {}

    def get(self, route, params=None):
        url = self.base_url + route
        return requests.get(url, params, headers=self.headers).json()

    def post(self, route, data=None):
        url = self.base_url + route

        logging.debug('POST json: ' + json.dumps(data, indent=4))

        res = requests.post(url, json=data, headers=self.headers)

        # res.json() will fail if the response is empty/invalid JSON
        try:
            logging.debug('Response json: ' + json.dumps(res.json(), indent=4))
            return res.json()
        except json.decoder.JSONDecodeError:
            return None

    def add_header(self, header):
        self.headers.update(header)

class StandardNotesAPI:

    def check_mfa_error(self, res):
        if 'error' in res:
            if 'tag' in res['error'] and res['error']['tag'] == 'mfa-required':
                mfa_code = input('Enter your two-factor authentication code: ')
                self.mfa_data = {res['error']['payload']['mfa_key']: mfa_code}
                return True
            else:
                raise SNAPIException(res['error']['message'])



    def check_jwt_validity(self):
        # this will return None if our jwt has been invalidated
        res = self.api.post('/items/sync', dict(limit=1))
        return res


    def get_auth_params_for_email(self):
        res = self.api.get('/auth/params', dict(email=self.username,
                                                api=API_VERSION,
                                                **self.mfa_data))
        if self.check_mfa_error(res):
            return self.get_auth_params_for_email()
        else:
            return res

    def gen_keys(self, password):
        pw_info = self.get_auth_params_for_email()

        email = pw_info['identifier']
        version = pw_info['version']
        pw_nonce = pw_info['pw_nonce']

        if version == '001':
            print('Old authentication protocol detected. This version is not '
                  'supported by standardnotes-fs. Please resync all of '
                  'your notes by following the instructions here:\n'
                  'https://standardnotes.org/help/resync')
            sys.exit(1)
        elif version == '002':
            pw_salt = pw_info['pw_salt']
        elif version == '003':
            pw_cost = pw_info['pw_cost']
            pw_salt = self.encryption_helper.generate_salt_from_nonce(
                email, version, str(pw_cost), pw_nonce)
            return self.encryption_helper.generate_password_and_key(
                password, pw_salt, pw_cost)
        elif version == '004':
            return self.encryption_helper.generate_password_and_key_004(
                password, email, pw_nonce
            )

    def sign_in(self, keys):
        self.keys = keys

        # if jwt is present, we don't need to authenticate again
        if 'jwt' in self.keys:
            self.api.add_header(dict(Authorization='Bearer ' + self.keys['jwt']))
            if self.check_jwt_validity():
                self.encryption_version = '003'
                return self.keys

        res = self.api.post('/auth/sign_in', dict(email=self.username,
                                                    password=self.keys['pw'],
                                                    api=API_VERSION,
                                                    ephemeral=False,
                                                    **self.mfa_data))

        print("sign_in->res", res)

        if self.check_mfa_error(res):
            self.keys = self.sign_in(keys)
        else:
            # v003
            jwt = res.get('token')
            if jwt is not None:
                self.api.add_header(dict(Authorization='Bearer ' + jwt))
                self.keys['jwt'] = jwt
                self.encryption_version = '003'
                return self.keys
            # v004
            try:
                jwt = res['session']['access_token']
                self.api.add_header(dict(Authorization='Bearer ' + jwt))
                self.keys['jwt'] = jwt
                self.encryption_version = '004'
                return self.keys
            except Exception as e:
                print(e)


    def sync(self, dirty_items):
        items = self.handle_dirty_items(dirty_items)

        # 0003
        if self.encryption_version == '003':
            data = dict(
                sync_token=self.sync_token,
                items=items,
                api=API_VERSION,
            )

            response = self.api.post('/items/sync', data)

            if not response:
                raise SNAPIException('Error accessing the Standard Notes API.')

            self.sync_token = response['sync_token']
            return self.handle_response_items(response)


        elif self.encryption_version == '004':
            data = dict(items=items, compute_integrity=True, limit=150, api=API_VERSION)
            response = self.api.post('/items/sync', data)
            return self.handle_response_items_004(response)


    def handle_dirty_items(self, dirty_items):
        items = self.encryption_helper.encrypt_dirty_items(
                dirty_items, self.keys)
        return items

    def handle_response_items(self, response):
        valid_items = [item for item in response['retrieved_items']
            if item['content_type'] in ALLOWED_ITEM_TYPES]
        response_items = self.encryption_helper.decrypt_response_items(
                valid_items, self.keys)
        saved_items = self.encryption_helper.decrypt_response_items(
                response['saved_items'], self.keys)
        return dict(response_items=response_items, saved_items=saved_items)

    def handle_response_items_004(self, response):
        # keys: 'retrieved_items', 'saved_items', 'conflicts', 'sync_token', 'cursor_token', 'integrity_hash']

        from base64 import b64decode, b64encode
        from binascii import hexlify, unhexlify
        from copy import deepcopy
        import json
        import argon2
        from Crypto.Cipher import ChaCha20_Poly1305

        print("response", response)
        print("retrieved_items:", response["retrieved_items"])
        print("sync_token", response["sync_token"])

        master_key = self.keys['master_key']
        default_items_key = None
        notes = {}
        response_items = []

        print("len of sync['retrieved_items']", len(response["retrieved_items"]))
        for item in response["retrieved_items"]:
            uuid = item["uuid"]
            content = item["content"]
            content_type = item["content_type"]
            enc_item_key = item["enc_item_key"]

            print()
            print("Processing item", uuid)
            print("    content_type", content_type)
            print("    Decrypting enc_item_key")

            version, nonce, ciphertext, encoded_authenticated_data = enc_item_key.split(":")
            authenticated_data = json.loads(b64decode(encoded_authenticated_data).decode())

            print("        version:", version)
            print("        nonce:", nonce)
            print("        ciphertext:", ciphertext)
            print("        auth data:", authenticated_data)

            if content_type == "SN|ItemsKey":
                key = master_key
            else:
                key = default_items_key

            print("        key:", key)
            cipher = ChaCha20_Poly1305.new(key=unhexlify(key), nonce=unhexlify(nonce))
            item_key = cipher.decrypt(b64decode(ciphertext))[:-16].decode()
            print("        item_key", item_key)

            print("    Decrypting content")

            version, nonce, ciphertext, encoded_authenticated_data = content.split(":")
            authenticated_data = json.loads(b64decode(encoded_authenticated_data).decode())

            print("        version:", version)
            print("        nonce:", nonce)
            print("        ciphertext:", ciphertext)
            print("        auth data:", authenticated_data)

            cipher = ChaCha20_Poly1305.new(key=unhexlify(item_key), nonce=unhexlify(nonce))
            plaintext = cipher.decrypt(b64decode(ciphertext))[:-16].decode()
            print("        plaintext", plaintext)

            plainjson = json.loads(plaintext)
            print("        plainjson:", plainjson)

            if plainjson.get("isDefault", False):
                default_items_key = plainjson["itemsKey"]

            if content_type == "Note":
                notes[plainjson["title"]] = plainjson["text"]
                dec_content = plainjson
                dec_item = deepcopy(item)
                dec_item['content'] = dec_content
                response_items.append(dec_item)

 
        print()
        print()
        print("Here are your notes:")

        for title, text in notes.items():
            print()
            print(title)
            print(text)


        return dict(response_items=response_items, saved_items=[])

    def __init__(self, base_url, username):
        self.encryption_helper = EncryptionHelper(sn_api=self)
        self.sync_token = None
        self.mfa_data = {}

        self.api = RESTAPI(base_url)
        self.username = username
        self.encryption_version = None
        self.default_items_key = None
