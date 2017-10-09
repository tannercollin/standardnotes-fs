import hashlib, hmac, json
from base64 import b64encode, b64decode
from binascii import hexlify, unhexlify
from Crypto.Cipher import AES
from Crypto.Random import random
from copy import deepcopy
import sys

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

        if content[:3] == '001':
            print('Old encryption protocol detected. This version is not '
                  'supported by standardnotes-fs. Please resync all of '
                  'your notes by following the instructions here:\n'
                  'https://standardnotes.org/help/resync')
            sys.exit(1)
        elif content[:3] == '002':
            item_key = self.pure_decryptString002(enc_item_key, keys['mk'], keys['ak'], uuid)
            item_key_length = len(item_key)
            item_ek = item_key[:item_key_length//2]
            item_ak = item_key[item_key_length//2:]

            dec_content = self.pure_decryptString002(content, item_ek, item_ak, uuid)
        else:
            print('Invalid protocol version. This could indicate tampering or '
                  'that something is wrong with the server. Exiting.')
            sys.exit(1)

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
            print('UUID does not match. This could indicate tampering or '
                  'that something is wrong with the server. Exiting.')
            sys.exit(1)

        string_to_auth = ':'.join([version, uuid, IV, ciphertext])
        local_auth_hash = hmac.new(unhexlify(auth_key), string_to_auth.encode(), 'sha256').digest()
        local_auth_hash = hexlify(local_auth_hash).decode()

        if local_auth_hash != auth_hash:
            print('Auth hash does not match. This could indicate tampering or '
                  'that something is wrong with the server. Exiting.')
            sys.exit(1)

        cipher = AES.new(unhexlify(encryption_key), AES.MODE_CBC, unhexlify(IV))
        result = cipher.decrypt(b64decode(ciphertext))
        result = result[:-result[-1]] # remove PKCS#7 padding
        result = result.decode()

        return result
