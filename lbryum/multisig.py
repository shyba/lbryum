import logging

from lbryschema.address import hash_160_bytes_to_address

from lbryum.transaction import Transaction
from lbryum.hashing import hash_160
from lbryum.account import Account
from lbryum.bip32 import BIP32_Account

log = logging.getLogger(__name__)


class Multisig_Account(BIP32_Account):
    def __init__(self, v):
        self.m = v.get('m', 2)
        BIP32_Account.__init__(self, v)
        self.xpub_list = v['xpubs']

    def dump(self):
        d = Account.dump(self)
        d['xpubs'] = self.xpub_list
        d['m'] = self.m
        return d

    def get_pubkeys(self, for_change, n):
        return self.get_pubkey(for_change, n)

    def derive_pubkeys(self, for_change, n):
        return map(lambda x: self.derive_pubkey_from_xpub(x, for_change, n),
                   self.get_master_pubkeys())

    def redeem_script(self, for_change, n):
        pubkeys = self.get_pubkeys(for_change, n)
        return Transaction.multisig_script(sorted(pubkeys), self.m)

    def pubkeys_to_address(self, pubkeys):
        redeem_script = Transaction.multisig_script(sorted(pubkeys), self.m)
        address = hash_160_bytes_to_address(hash_160(redeem_script.decode('hex')), 5)
        return address

    def get_address(self, for_change, n):
        return self.pubkeys_to_address(self.get_pubkeys(for_change, n))

    def get_master_pubkeys(self):
        return self.xpub_list

    def get_type(self):
        return 'Multisig %d of %d' % (self.m, len(self.xpub_list))
