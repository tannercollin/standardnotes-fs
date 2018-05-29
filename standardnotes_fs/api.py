import requests

from standardnotes_fs.crypt import EncryptionHelper

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
        return requests.post(url, json=data, headers=self.headers).json()

    def add_header(self, header):
        self.headers.update(header)

class StandardNotesAPI:
    encryption_helper = EncryptionHelper()
    sync_token = None

    def get_auth_params_for_email(self):
        return self.api.get('/auth/params', dict(email=self.username))

    def gen_keys(self, password):
        pw_info = self.get_auth_params_for_email()

        if 'error' in pw_info:
            raise SNAPIException(pw_info['error']['message'])

        return self.encryption_helper.pure_generate_password_and_key(
                password, pw_info['pw_salt'], pw_info['pw_cost'])

    def sign_in(self, keys):
        self.keys = keys
        res = self.api.post('/auth/sign_in', dict(email=self.username,
                                                  password=self.keys['pw']))
        if 'error' in res:
            raise SNAPIException(res['error']['message'])

        self.api.add_header(dict(Authorization='Bearer ' + res['token']))

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
        response_items = self.encryption_helper.decrypt_response_items(
                response['retrieved_items'], self.keys)
        saved_items = self.encryption_helper.decrypt_response_items(
                response['saved_items'], self.keys)
        return dict(response_items=response_items, saved_items=saved_items)

    def __init__(self, base_url, username):
        self.api = RESTAPI(base_url)
        self.username = username
