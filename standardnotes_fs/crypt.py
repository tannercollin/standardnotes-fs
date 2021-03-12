from base64 import b64decode, b64encode
from binascii import hexlify, unhexlify
from copy import deepcopy
import hashlib
import hmac
import json
import logging
import sys

import argon2
from Crypto.Cipher import AES, ChaCha20_Poly1305
from Crypto.Random import random
from Crypto.Util import Padding

BITS_PER_HEX_DIGIT = 4

PASS_KEY_LEN = 96
AES_KEY_LEN = 256
AES_STR_KEY_LEN = AES_KEY_LEN // BITS_PER_HEX_DIGIT
AES_IV_LEN = 128
AES_STR_IV_LEN = AES_IV_LEN // BITS_PER_HEX_DIGIT

class EncryptionHelper:
    def generate_salt_from_nonce(self, email, version, pw_cost, pw_nonce):
        string_to_hash = ':'.join([email, 'SF', version, pw_cost, pw_nonce])
        output = hashlib.sha256(string_to_hash.encode()).hexdigest()

        return output

    def generate_password_and_key(self, password, pw_salt, pw_cost):
        output = hashlib.pbkdf2_hmac(
                'sha512', password.encode(), pw_salt.encode(), pw_cost,
                dklen=PASS_KEY_LEN)
        output = hexlify(output).decode()

        output_length = len(output)
        split_length = output_length // 3
        pw = output[0 : split_length]
        mk = output[split_length : split_length * 2]
        ak = output[split_length * 2 : split_length * 3]

        return dict(pw=pw, mk=mk, ak=ak)

    def generate_password_and_key_004(
                self, password, email, pw_nonce
            ):
        string_to_hash = email + ":" + pw_nonce
        print("Hashing:", string_to_hash)
        salt = hashlib.sha256(string_to_hash.encode()).hexdigest()[:32]
        print("Salt:", salt)

        argon2_hash = argon2.low_level.hash_secret_raw(
            secret=password.encode(),
            salt=unhexlify(salt),
            time_cost=5,
            memory_cost=65536,
            parallelism=1,
            hash_len=64,
            type=argon2.Type.ID,
        )
        derived_key = hexlify(argon2_hash).decode()

        print("Derived key:", derived_key, "Length:", len(derived_key))

        master_key = derived_key[:64]
        server_password = derived_key[64:]

        print()
        print("Master key:", master_key)
        print("Server password:", server_password)

        return dict(server_password=server_password, master_key=master_key, 
           pw=server_password)

    def encrypt_dirty_items(self, dirty_items, keys):
        return [self.encrypt_item(item, keys) for item in dirty_items]

    def decrypt_response_items(self, response_items, keys):
        return [self.decrypt_item(item, keys) for item in response_items]

    def encrypt_item(self, item, keys):
        uuid = item['uuid']
        content = json.dumps(item['content'])

        logging.debug('Encrypting item {} with content: {}'.format(uuid, content))

        # all this is to follow the Standard Notes spec
        item_key = hex(random.getrandbits(AES_KEY_LEN * 2))
        # remove '0x', pad with 0's, then split in half
        item_key = item_key[2:].rjust(AES_STR_KEY_LEN * 2, '0')
        item_ek = item_key[:AES_STR_KEY_LEN]
        item_ak = item_key[AES_STR_KEY_LEN:]

        enc_item = deepcopy(item)
        enc_item['content'] = self.encrypt_string_003(
                content, item_ek, item_ak, uuid)
        enc_item['enc_item_key'] = self.encrypt_string_003(
                item_key, keys['mk'], keys['ak'], uuid)

        return enc_item

    def decrypt_item(self, item, keys):
        if item['deleted']:
            return item

        uuid = item['uuid']
        content = item['content']
        enc_item_key = item['enc_item_key']
        version = content[:3]

        logging.debug('Decrypting item {} of version {} with content: {}'.format(uuid, version, content))

        if version == '001' or version == '002':
            print('Old encryption protocol detected. This version is not '
                  'supported by standardnotes-fs. Please resync all of '
                  'your notes by following the instructions here:\n'
                  'https://standardnotes.org/help/resync')
            sys.exit(1)
        elif version == '003':
            item_key = self.decrypt_string_003(
                    enc_item_key, keys['mk'], keys['ak'], uuid)
            item_key_length = len(item_key)
            item_ek = item_key[:item_key_length//2]
            item_ak = item_key[item_key_length//2:]

            dec_content = self.decrypt_string_003(
                    content, item_ek, item_ak, uuid)
        elif version == '004':
            content_type = item["content_type"]
            print(item, uuid, content, enc_item_key, version)

            version, nonce, ciphertext, encoded_authenticated_data = enc_item_key.split(":")
            authenticated_data = json.loads(b64decode(encoded_authenticated_data).decode())

            print("        version:", version)
            print("        nonce:", nonce)
            print("        ciphertext:", ciphertext)
            print("        auth data:", authenticated_data)

            if content_type == "SN|ItemsKey":
                key = keys['master_key']
            else:
                key = self.sn_api.default_items_key

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

            if plainjson.get("isDefault", False):
                self.sn_api.default_items_key = plainjson["itemsKey"]

            if content_type == "Note":
                notes[plainjson["title"]] = plainjson["text"]


            dec_content = plainjson

        dec_item = deepcopy(item)
        dec_item['content'] = json.loads(dec_content)

        return dec_item

    def encrypt_string_003(self, string_to_encrypt, encryption_key,
                                auth_key, uuid):
        IV = hex(random.getrandbits(AES_IV_LEN))
        IV = IV[2:].rjust(AES_STR_IV_LEN, '0') # remove '0x', pad with 0's

        cipher = AES.new(unhexlify(encryption_key), AES.MODE_CBC, unhexlify(IV))
        pt = string_to_encrypt.encode()
        padded_pt = Padding.pad(pt, AES.block_size)
        ciphertext = b64encode(cipher.encrypt(padded_pt)).decode()

        string_to_auth = ':'.join(['003', uuid, IV, ciphertext])
        auth_hash = hmac.new(
                unhexlify(auth_key), string_to_auth.encode(), 'sha256').digest()
        auth_hash = hexlify(auth_hash).decode()

        result = ':'.join(['003', auth_hash, uuid, IV, ciphertext])

        return result

    def decrypt_string_003(self, string_to_decrypt, encryption_key,
                                auth_key, uuid):
        components = string_to_decrypt.split(':')
        if len(components) == 6:
            version, auth_hash, local_uuid, IV, ciphertext, auth_params = components
        else:
            version, auth_hash, local_uuid, IV, ciphertext = components

        if local_uuid != uuid:
            print('Note UUID does not match.')
            print('This could be caused by a conflicted copy of a note.')
            print('Rename or delete the conflicted copy to fix.')
            print('Could also be a sign of tampering. Exiting for security...')
            logging.debug('UUID: {}, Local UUID: {}'.format(uuid, local_uuid))
            sys.exit(1)

        string_to_auth = ':'.join([version, uuid, IV, ciphertext])
        local_auth_hash = hmac.new(
                unhexlify(auth_key), string_to_auth.encode(), 'sha256').digest()

        auth_hash = unhexlify(auth_hash)
        if not hmac.compare_digest(local_auth_hash, auth_hash):
            print('Auth hash does not match. This could indicate tampering or '
                  'that something is wrong with the server. Exiting.')
            logging.debug('Auth Hash: {}, Local Auth Hash: {}'.format(auth_hash, local_auth_hash))
            sys.exit(1)

        cipher = AES.new(unhexlify(encryption_key), AES.MODE_CBC, unhexlify(IV))
        result = cipher.decrypt(b64decode(ciphertext))
        result = Padding.unpad(result, AES.block_size).decode()

        return result

    def decrypt_string_004(self, string_to_decrypt, encryption_key,
                                auth_key, uuid):
        pass

    def __init__(self, sn_api=None):
        """allow for a pointer back to an instantiating StandardNoteAPI object"""
        self.sn_api = sn_api