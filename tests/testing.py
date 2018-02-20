import time
import threading
from collections import OrderedDict

from lbryum import commands, wallet, transaction, bip32, network, blockchain, lbrycrd, contacts
from lbryum.constants import TYPE_ADDRESS, TYPE_CLAIM, TYPE_SUPPORT, TYPE_SCRIPT

from test_data import PUBKEY


class MocStore(dict):
    def __init__(self):
        self.lock = threading.Lock()
        self.write_called = 0

    def put(self, key, val):
        self[key] = val

    def write(self):
        self.write_called += 1


class MocContacts(contacts.Contacts):
    def __init__(self):
        pass


class MocKeyring:
    def __init__(self):
        self.set_password_called = False

    def set_password(self, app, username, password):
        self.set_password_called = app, username, password


class MocWallet(wallet.NewWallet):

    def __init__(self):
        super(MocWallet, self).__init__(MocStore())
        self.accounts = {'0': bip32.BIP32_Account({'xpub': PUBKEY})}
        self.send_tx_connected = True
        self.send_tx_success = True
        self.sent_transactions = []
        self.height = 0
        self.transactions = OrderedDict()

    @property
    def next_height(self):
        self.height += 1
        return self.height

    @property
    def last_transaction(self):
        return next(reversed(self.transactions.values()))

    def send_tx(self, tx, timeout=300):
        self.sent_transactions.append(tx)
        if not self.send_tx_connected:
            raise Exception("Not connected.")
        tx.raw = tx.serialize()
        return self.send_tx_success, tx.raw

    def sign_transaction(self, tx, password):
        for txi in tx._inputs:
            if 'signatures' not in txi:
                txi.update({
                    'height': self.next_height,
                    'signatures': [None],
                    'pubkeys': ['02e61d176da16edd1d258a200ad9759ef63adf8e14cd97f53227bae35cdb84d2f6'],
                    'x_pubkeys': ['02e61d176da16edd1d258a200ad9759ef63adf8e14cd97f53227bae35cdb84d2f6']
                })

    def add_address_transaction(self, amount):
        out_address = self.create_new_address()
        return self._add_transaction(
            out_address, amount,
            (TYPE_ADDRESS, out_address, amount)
        )

    def add_claim_transaction(self, name, amount, value=''):
        out_address = self.create_new_address()
        tx = self._add_transaction(
            out_address, amount,
            (TYPE_CLAIM | TYPE_SCRIPT, ((name, value), out_address), amount)
        )
        self.claimtrie_transactions[tx.hash() + ':0'] = tx._outputs[0]
        return tx

    def add_support_transaction(self, name, amount, claim_id, claim_addr):
        out_address = self.create_new_address()
        return self._add_transaction(
            out_address, amount,
            (TYPE_ADDRESS | TYPE_SUPPORT, ((name, claim_id), claim_addr), amount)
        )

    def _add_transaction(self, out_address, out_amount, out_data):
        in_address = self.create_new_address()
        tx = transaction.Transaction.from_io(
            [{
                'address': in_address,
                'prevout_hash': '3140eb24b43386f35ba69e3875eb6c93130ac66201d01c58f598defc949a5c2a',
                'prevout_n': 0,
            }],
            [
                out_data
            ]
        )
        self.sign_transaction(tx, '')
        tx.raw = tx.serialize()
        tx_hash = tx.hash()
        tx_height = self.next_height
        self.history.setdefault(out_address, [])
        self.history[out_address].append([tx_hash, tx_height])
        self.txo[tx_hash] = {
            out_address: [(0, out_amount, False)]
        }
        self.transactions[tx_hash] = tx
        return tx

    def make_last_tx_verified(self):
        tx = self.last_transaction
        out_address = self.txo[tx.hash()].keys()[0]
        height = self.history[out_address][0][1]
        self.verified_tx[tx.hash()] = (height, time.time(), 1)


class MocBlockchain(blockchain.LbryCrd):

    def __init__(self, config, network):
        chain = self.BLOCKCHAIN_NAME
        params = blockchain.blockchain_params
        script_address = params[chain]['script_address']
        script_address_prefix = params[chain]['script_address_prefix']
        pubkey_address = params[chain]['pubkey_address']
        pubkey_address_prefix = params[chain]['pubkey_address_prefix']
        lbrycrd.SCRIPT_ADDRESS = (script_address, script_address_prefix)
        lbrycrd.PUBKEY_ADDRESS = (pubkey_address, pubkey_address_prefix)
        super(MocBlockchain, self).__init__(config, network)
        self.respond_with_header = None

    def read_header(self, block_height):
        return self.respond_with_header


class MocNetwork(network.Network):

    def __init__(self, responses=None):
        self.responses = responses or {}
        self.config = network.SimpleConfig({
            'lbryum_path': '.',
            'chain': 'lbrycrd_main'
        })
        self.default_server = 'lbry.io:50001:t'
        self.heights = {self.default_server: 1}
        self.blockchain = MocBlockchain(self.config, self)

    def send(self, request, callback):
        assert len(request) == 1, 'Mock network only supports one request at a time.'
        request = request[0]
        callback({'result': self.responses[request[0]](request[1])})


class MocCommands(commands.Commands):
    def __init__(self, config=None, wallet=None, network=None):
        self.config = config or {}
        self.wallet = wallet or MocWallet()
        self.network = network or MocNetwork()
        self.contacts = MocContacts()
        self._password = None
        self._keyring = MocKeyring()

