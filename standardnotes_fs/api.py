import json
import requests
import sys

from standardnotes_fs.crypt import EncryptionHelper

ALLOWED_ITEM_TYPES = ['Note', 'Tag']

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
        res = requests.post(url, json=data, headers=self.headers)

        # res.json() will fail if the response is empty/invalid JSON
        try:
            return res.json()
        except json.decoder.JSONDecodeError:
            return None

    def add_header(self, header):
        self.headers.update(header)

class StandardNotesAPI:
    encryption_helper = EncryptionHelper()
    sync_token = None
    mfa_data = {}

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
                                                **self.mfa_data))
        if self.check_mfa_error(res):
            return self.get_auth_params_for_email()
        else:
            return res

    def gen_keys(self, password):
        pw_info = self.get_auth_params_for_email()

        email = pw_info['identifier']
        version = pw_info['version']
        pw_cost = pw_info['pw_cost']
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
            pw_salt = self.encryption_helper.generate_salt_from_nonce(
                email, version, str(pw_cost), pw_nonce)

        return self.encryption_helper.generate_password_and_key(
                password, pw_salt, pw_cost)

    def sign_in(self, keys):
        self.keys = keys

        # if jwt is present, we don't need to authenticate again
        if 'jwt' in self.keys:
            self.api.add_header(dict(Authorization='Bearer ' + self.keys['jwt']))
            if self.check_jwt_validity():
                return self.keys

        res = self.api.post('/auth/sign_in', dict(email=self.username,
                                                    password=self.keys['pw'],
                                                    **self.mfa_data))

        if self.check_mfa_error(res):
            self.keys = self.sign_in(keys)
        else:
            jwt = res['token']
            self.api.add_header(dict(Authorization='Bearer ' + jwt))
            self.keys['jwt'] = jwt

        return self.keys

    def sync(self, dirty_items):
        items = self.handle_dirty_items(dirty_items)
        response = self.api.post('/items/sync', dict(sync_token=self.sync_token,
                                                     items=items))
        self.sync_token = response['sync_token']
        return self.handle_response_items(response)

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

    def __init__(self, base_url, username):
        self.api = RESTAPI(base_url)
        self.username = username
