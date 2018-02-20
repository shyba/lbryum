import logging

from lbryschema.base import b58encode_with_checksum, b58decode_strip_checksum

from lbryum.util import rev_hex, int_to_hex, is_extended_pubkey
from lbryum.lbrycrd import deserialize_xkey, bip32_public_derivation
from lbryum.lbrycrd import CKD_pub, bip32_private_key
from lbryum.account import Account

log = logging.getLogger(__name__)


class BIP32_Account(Account):
    def __init__(self, v):
        Account.__init__(self, v)
        self.xpub = v['xpub']
        self.xpub_receive = None
        self.xpub_change = None

    def correct_pubkeys(self):
        """
        Wallets could have duplicate pubkeys and skip pubkey generation
        for the nth sequence, due to a race condition bug
        (see https://github.com/lbryio/lbryum/pull/147)

        return True if problem was found and corrected,
        retun False if no problem was found
        """
        correction_made = False
        if self._check_pubkeys(self.receiving_pubkeys, False):
            self.receiving_pubkeys = self._correct_pubkeys(self.receiving_pubkeys, False)
            correction_made = True
        if self._check_pubkeys(self.change_pubkeys, True):
            self.change_pubkeys = self._correct_pubkeys(self.change_pubkeys, True)
            correction_made = True
        return correction_made

    def _check_pubkeys(self, pubkeys, for_change):
        pubkeys_set = set(pubkeys)
        duplicate_key_found = len(pubkeys_set) != len(pubkeys)
        if duplicate_key_found:
            log.warn("Duplicate key found, will correct, this may take a minute")

        expected_last_pubkey = self.derive_pubkeys(for_change, len(pubkeys)-1)
        last_pubkey_incorrect = expected_last_pubkey != pubkeys[-1]
        if last_pubkey_incorrect:
            log.warn("Last pubkey was not as expected, will correct, this make take a minute")
        return duplicate_key_found or last_pubkey_incorrect

    def _correct_pubkeys(self, pubkeys, for_change):
        """
        Try to re-derive the nth pubkeys and add them
        in order, while making sure every pubkey gets added
        """
        pubkeys_set = set(pubkeys)
        corrected_pubkeys = []
        index = 0
        while len(pubkeys_set) > 0:
            expected_pubkey = self.derive_pubkeys(for_change, index)
            if expected_pubkey in pubkeys_set:
                pubkeys_set.remove(expected_pubkey)
            corrected_pubkeys.append(expected_pubkey)
            log.debug("Appending pubkey:%s", expected_pubkey)
            if index >= len(pubkeys) or expected_pubkey != pubkeys[index]:
                log.debug("Correction made, from %s to %s", expected_pubkey, pubkeys[index])
            index += 1
            if index > len(pubkeys) + 100:
                raise Exception(
                    "Critical error found when correcting public key, exceeded max key generation")
        return corrected_pubkeys

    def dump(self):
        d = Account.dump(self)
        d['xpub'] = self.xpub
        return d

    def first_address(self):
        pubkeys = self.derive_pubkeys(0, 0)
        addr = self.pubkeys_to_address(pubkeys)
        return addr, pubkeys

    def get_master_pubkeys(self):
        return [self.xpub]

    @classmethod
    def derive_pubkey_from_xpub(cls, xpub, for_change, n):
        _, _, _, c, cK = deserialize_xkey(xpub)
        for i in [for_change, n]:
            cK, c = CKD_pub(cK, c, i)
        return cK.encode('hex')

    def get_pubkey_from_xpub(self, xpub, for_change, n):
        xpubs = self.get_master_pubkeys()
        i = xpubs.index(xpub)
        pubkeys = self.get_pubkeys(for_change, n)
        return pubkeys[i]

    def derive_pubkeys(self, for_change, n):
        xpub = self.xpub_change if for_change else self.xpub_receive
        if xpub is None:
            xpub = bip32_public_derivation(self.xpub, "", "/%d" % for_change)
            if for_change:
                self.xpub_change = xpub
            else:
                self.xpub_receive = xpub
        _, _, _, c, cK = deserialize_xkey(xpub)
        cK, c = CKD_pub(cK, c, n)
        result = cK.encode('hex')
        return result

    def get_private_key(self, sequence, wallet, password):
        out = []
        xpubs = self.get_master_pubkeys()
        roots = [k for k, v in wallet.master_public_keys.iteritems() if v in xpubs]
        for root in roots:
            xpriv = wallet.get_master_private_key(root, password)
            if not xpriv:
                continue
            _, _, _, c, k = deserialize_xkey(xpriv)
            pk = bip32_private_key(sequence, k, c)
            out.append(pk)
        return out

    def get_type(self):
        return 'Standard 1 of 1'

    def get_xpubkeys(self, for_change, n):
        # unsorted
        s = ''.join(map(lambda x: int_to_hex(x, 2), (for_change, n)))
        xpubs = self.get_master_pubkeys()
        return map(lambda xpub: 'ff' + b58decode_strip_checksum(xpub).encode('hex') + s, xpubs)

    @classmethod
    def parse_xpubkey(cls, pubkey):
        assert is_extended_pubkey(pubkey)
        pk = pubkey.decode('hex')
        pk = pk[1:]
        xkey = b58encode_with_checksum(pk[0:78])
        dd = pk[78:]
        s = []
        while dd:
            n = int(rev_hex(dd[0:2].encode('hex')), 16)
            dd = dd[2:]
            s.append(n)
        assert len(s) == 2
        return xkey, s

    def get_name(self, k):
        return "Main account" if k == '0' else "Account " + k
