import binascii
import unittest

from lbryschema.address import hash_160_bytes_to_address, address_to_hash_160, is_address

from lbryum import claims
from lbryum import commands
from lbryum.hashing import Hash, PoWHash
from lbryum.lbrycrd import claim_id_hash, calculate_lbrycrd_min_fee
from lbryum.constants import TYPE_CLAIM, TYPE_ADDRESS, LBRYCRD_MIN_FEE_PER_NAMECLAIM_CHAR
from lbryum.util import rev_hex


def get_powhash(input_str):
    out = PoWHash(input_str)
    hex_out = out.encode('hex_codec')
    # need to reformat to little endian int
    out_str = ''
    for i in range(64, 0, -2):
        out_str += hex_out[i - 2:i]
    return out_str


class Test_Lbry(unittest.TestCase):
    def test_hash(self):
        test = get_powhash("test string")
        value = "485f3920d48a0448034b0852d1489cfa475341176838c7d36896765221be35ce"
        self.assertEqual(test, value)

        test = get_powhash("a" * 70)
        value = "eb44af2f41e7c6522fb8be4773661be5baa430b8b2c3a670247e9ab060608b75"
        self.assertEqual(test, value)

        test = get_powhash("d" * 140)
        value = "74044747b7c1ff867eb09a84d026b02d8dc539fb6adcec3536f3dfa9266495d9"
        self.assertEqual(test, value)

    def test_verify_proof(self):
        claim1_name = 97  # 'a'
        claim1_txid = 'bd9fa7ffd57d810d4ce14de76beea29d847b8ac34e8e536802534ecb1ca43b68'
        claim1_outpoint = 0
        claim1_height = 10
        claim1_node_hash = claims.get_hash_for_outpoint(
            binascii.unhexlify(claim1_txid)[::-1], claim1_outpoint, claim1_height)

        claim2_name = 98  # 'b'
        claim2_txid = 'ad9fa7ffd57d810d4ce14de76beea29d847b8ac34e8e536802534ecb1ca43b68'
        claim2_outpoint = 1
        claim2_height = 5
        claim2_node_hash = claims.get_hash_for_outpoint(
            binascii.unhexlify(claim2_txid)[::-1], claim2_outpoint, claim2_height)
        to_hash1 = claim1_node_hash
        hash1 = Hash(to_hash1)
        to_hash2 = chr(claim1_name) + hash1 + chr(claim2_name) + claim2_node_hash

        root_hash = Hash(to_hash2)

        proof = {
            'last takeover height': claim1_height, 'txhash': claim1_txid, 'nOut': claim1_outpoint,
            'nodes': [
                {'children': [
                    {'character': 97},
                    {
                        'character': 98,
                        'nodeHash': claim2_node_hash[::-1].encode('hex')
                    }
                ]},
                {'children': []},
            ]
        }
        out = claims.verify_proof(proof, root_hash[::-1].encode('hex'), 'a')
        self.assertEqual(out, True)

    def test_commands_wrapper_for_verify_proof(self):
        result = {}
        out = commands.Commands._verify_proof('test', 'test', result, 100, 10)
        self.assertTrue('error' in out)

        # valid proof and root has taken from test_verify_proof()
        valid_proof = {'last takeover height': 10,
                       'txhash': 'bd9fa7ffd57d810d4ce14de76beea29d847b8ac34e8e536802534ecb1ca43b68',
                       'nodes': [{'children': [{'character': 97}, {
                           'nodeHash': '5aa71fb53f646dd5cbde28fce95d89a0e9720f8ca4f87d66a52aa9e7aa0a1552',
                           'character': 98}]}, {'children': []}], 'nOut': 0}
        valid_root_hash = '198e65bd4c3b66681fac1b8a0b9850cf28dc5df33a86b67cbd72cc7e5d93ba49'
        result = {'proof': valid_proof, 'supports': []}

        out = commands.Commands._verify_proof('a', valid_root_hash, result, 100, 10)
        self.assertTrue('error' in out)

    def test_claimid_hash(self):
        txid = "4d08012feefec192bdb45495dcedc171a56d369539ce2d589e3e1ec81a882bb4"
        nout = 1
        claim_id = "a438fc7701e10e0e5c41d7a342be1190d9bed57b"
        out = claim_id_hash(rev_hex(txid).decode('hex'), nout)
        self.assertEqual(claim_id, rev_hex(out.encode('hex')))

    def test_address_encode_decode(self):
        valid_addr_hex = "be482f953ed0feda4fc5c4d012681b6119274993"
        self.assertEqual(hash_160_bytes_to_address(valid_addr_hex.decode('hex'), 0),
                         "bW5PZEvEBNPQRVhwpYXSjabFgbSw1oaHyR")
        self.assertEqual(address_to_hash_160("bW5PZEvEBNPQRVhwpYXSjabFgbSw1oaHyR"),
                         (0, "\xbeH/\x95>\xd0\xfe\xdaO\xc5\xc4\xd0\x12h\x1ba\x19'I\x93"))

    def test_address_encode_prefix_error(self):
        valid_addr_hex = "be482f953ed0feda4fc5c4d012681b6119274993"
        with self.assertRaises(Exception):
            hash_160_bytes_to_address(valid_addr_hex.decode('hex'), -1)
            hash_160_bytes_to_address(valid_addr_hex.decode('hex'), 2)
            hash_160_bytes_to_address(valid_addr_hex.decode('hex'), 2000)

    def test_address_decode_error(self):
        with self.assertRaises(Exception):
            address_to_hash_160("bW5PZEvEBNPQRVhwpYXSjabFgbSw1oaHR")
            address_to_hash_160("aW5PZEvEBNPQRVhwpYXSjabFgbSw1oaHyR")

    def test_is_address(self):
        self.assertFalse(is_address("something wrong"))
        self.assertFalse(is_address("123"))
        self.assertFalse(is_address("bYqee1aDgxA5oB4qr3PzjQ5xXzwGuyymH"))
        self.assertTrue(is_address("bYqee1aDgxA5oB4qr3PzjQ5xXzwGuyymH6"))
        self.assertTrue(is_address("bPJ9RPtyJSW9k5fGtJaxt3UhzUZSi59X9m"))

    def test_calculate_lbrycrd_min_fee(self):
        address = "bPJ9RPtyJSW9k5fGtJaxt3UhzUZSi59X9m"
        claim_name = '1234'
        val = ((claim_name, 'test'), address)
        outputs =[(TYPE_CLAIM | TYPE_ADDRESS, val, 1)]
        out = calculate_lbrycrd_min_fee(outputs)
        self.assertEqual(LBRYCRD_MIN_FEE_PER_NAMECLAIM_CHAR*4, out)

        val = (('12', 'test'), address)
        val2 = (('123', 'test'), address)
        outputs =[(TYPE_CLAIM, val, 1), (TYPE_CLAIM, val2, 1)]
        out = calculate_lbrycrd_min_fee(outputs)
        self.assertEqual(LBRYCRD_MIN_FEE_PER_NAMECLAIM_CHAR*5, out)

        outputs =[(TYPE_ADDRESS, address, 1)]
        out = calculate_lbrycrd_min_fee(outputs)
        self.assertEqual(0, out)



