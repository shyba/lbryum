import logging

from lbryschema.address import public_key_to_address
from lbryum.lbrycrd import pw_decode, pw_encode, address_from_private_key
from lbryum.errors import InvalidPassword

log = logging.getLogger(__name__)


class Account(object):
    def __init__(self, v):
        self.receiving_pubkeys = v.get('receiving', [])
        self.change_pubkeys = v.get('change', [])

        # addresses will not be stored on disk
        self.receiving_addresses = map(self.pubkeys_to_address, self.receiving_pubkeys)
        self.change_addresses = map(self.pubkeys_to_address, self.change_pubkeys)

    def dump(self):
        return {'receiving': self.receiving_pubkeys, 'change': self.change_pubkeys}

    def get_pubkey(self, for_change, n):
        pubkeys_list = self.change_pubkeys if for_change else self.receiving_pubkeys
        return pubkeys_list[n]

    def get_address(self, for_change, n):
        addr_list = self.change_addresses if for_change else self.receiving_addresses
        return addr_list[n]

    def get_pubkeys(self, for_change, n):
        return [self.get_pubkey(for_change, n)]

    def get_addresses(self, for_change):
        addr_list = self.change_addresses if for_change else self.receiving_addresses
        return addr_list[:]

    def derive_pubkeys(self, for_change, n):
        pass

    def create_new_address(self, for_change):
        pubkeys_list = self.change_pubkeys if for_change else self.receiving_pubkeys
        addr_list = self.change_addresses if for_change else self.receiving_addresses
        n = len(pubkeys_list)
        pubkeys = self.derive_pubkeys(for_change, n)
        address = self.pubkeys_to_address(pubkeys)
        pubkeys_list.append(pubkeys)
        addr_list.append(address)
        # print_msg(address)
        return address

    def pubkeys_to_address(self, pubkey):
        return public_key_to_address(pubkey.decode('hex'))

    def has_change(self):
        return True

    def get_name(self, k):
        return 'Main account'

    def redeem_script(self, for_change, n):
        return None

    def is_used(self, wallet):
        addresses = self.get_addresses(False)
        return any(wallet.address_is_old(a, -1) for a in addresses)

    def synchronize_sequence(self, wallet, for_change):
        limit = wallet.gap_limit_for_change if for_change else wallet.gap_limit
        while True:
            addresses = self.get_addresses(for_change)
            if len(addresses) < limit:
                address = self.create_new_address(for_change)
                wallet.add_address(address)
                continue
            if map(lambda a: wallet.address_is_old(a), addresses[-limit:]) == limit * [False]:
                break
            else:
                address = self.create_new_address(for_change)
                wallet.add_address(address)

    def synchronize(self, wallet):
        self.synchronize_sequence(wallet, False)
        self.synchronize_sequence(wallet, True)


class ImportedAccount(Account):
    def __init__(self, d):
        self.keypairs = d['imported']

    def synchronize(self, wallet):
        return

    def get_addresses(self, for_change):
        return [] if for_change else sorted(self.keypairs.keys())

    def get_pubkey(self, *sequence):
        for_change, i = sequence
        assert for_change == 0
        addr = self.get_addresses(0)[i]
        return self.keypairs[addr][0]

    def get_xpubkeys(self, for_change, n):
        return self.get_pubkeys(for_change, n)

    def get_private_key(self, sequence, wallet, password):
        for_change, i = sequence
        assert for_change == 0
        address = self.get_addresses(0)[i]
        pk = pw_decode(self.keypairs[address][1], password)
        # this checks the password
        if address != address_from_private_key(pk):
            raise InvalidPassword()
        return [pk]

    def has_change(self):
        return False

    def add(self, address, pubkey, privkey, password):
        self.keypairs[address] = (pubkey, pw_encode(privkey, password))

    def remove(self, address):
        self.keypairs.pop(address)

    def dump(self):
        return {'imported': self.keypairs}

    def get_name(self, k):
        return 'Imported keys'

    def update_password(self, old_password, new_password):
        for k, v in self.keypairs.items():
            pubkey, a = v
            b = pw_decode(a, old_password)
            c = pw_encode(b, new_password)
            self.keypairs[k] = (pubkey, c)
