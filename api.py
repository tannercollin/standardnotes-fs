import json, requests, time

from crypt import EncryptionHelper

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

    def addHeader(self, header):
        self.headers.update(header)

class StandardNotesAPI:
    encryption_helper = EncryptionHelper()
    sync_token = None

    def getAuthParamsForEmail(self):
        return self.api.get('/auth/params', dict(email=self.username))

    def genKeys(self, password):
        pw_info = self.getAuthParamsForEmail()

        if 'error' in pw_info:
            raise SNAPIException(pw_info['error']['message'])

        return self.encryption_helper.pure_generatePasswordAndKey(password, pw_info['pw_salt'], pw_info['pw_cost'])

    def signIn(self, keys):
        self.keys = keys
        res = self.api.post('/auth/sign_in', dict(email=self.username, password=self.keys['pw']))

        if 'error' in res:
            raise SNAPIException(res['error']['message'])

        self.api.addHeader(dict(Authorization='Bearer ' + res['token']))

    def sync(self, dirty_items):
        items = self.handleDirtyItems(dirty_items)
        response = self.api.post('/items/sync', dict(sync_token=self.sync_token, items=items))

        self.sync_token = response['sync_token']
        return self.handleResponseItems(response)

    def handleDirtyItems(self, dirty_items):
        items = self.encryption_helper.encryptDirtyItems(dirty_items, self.keys)
        return items

    def handleResponseItems(self, response):
        response_items = self.encryption_helper.decryptResponseItems(response['retrieved_items'], self.keys)
        saved_items = self.encryption_helper.decryptResponseItems(response['saved_items'], self.keys)
        return dict(response_items=response_items, saved_items=saved_items)

    def __init__(self, base_url, username):
        self.api = RESTAPI(base_url)
        self.username = username
