"""Passcode protection: sealed files, wrong passcodes, tampering, and never saving secrets in the clear."""
import json
import os
import shutil
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "addon", "script.kodisorter"))
import vault  # noqa: E402
from test_library_folders import load_default  # noqa: E402


class Crypto(unittest.TestCase):
    def test_round_trip_with_different_output_each_time(self):
        _, key = vault.setup("1234")
        a, b = vault.seal(key, b"secret"), vault.seal(key, b"secret")
        self.assertNotEqual(a, b)
        self.assertNotIn("secret", a)
        self.assertEqual(vault.unseal(key, a), b"secret")

    def test_long_data(self):
        _, key = vault.setup("1234")
        data = os.urandom(5000)
        self.assertEqual(vault.unseal(key, vault.seal(key, data)), data)

    def test_wrong_passcode_is_refused(self):
        state, key = vault.setup("1234")
        self.assertEqual(vault.unlock(state, "1234"), key)
        self.assertIsNone(vault.unlock(state, "9999"))
        _, other = vault.setup("9999")
        with self.assertRaises(vault.BadPasscode):
            vault.unseal(other, vault.seal(key, b"x"))

    def test_a_changed_file_is_refused(self):
        import base64
        _, key = vault.setup("1234")
        raw = bytearray(base64.b64decode(vault.seal(key, b"secret")))
        raw[20] ^= 1
        with self.assertRaises(vault.BadPasscode):
            vault.unseal(key, base64.b64encode(bytes(raw)).decode())

    def test_passcode_is_not_stored(self):
        state, _ = vault.setup("my-unique-passcode")
        self.assertNotIn("my-unique-passcode", json.dumps(state))


class Storage(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.data = os.path.join(self.tmp, "data")
        os.makedirs(self.data)
        d = self.d = load_default(self.data)
        props = self.props = {}

        class Win:
            def getProperty(self, k): return props.get(k, "")
            def setProperty(self, k, v): props[k] = v
            def clearProperty(self, k): props.pop(k, None)
        sys.modules["xbmcgui"].Window = lambda n: Win()
        sys.modules["xbmcgui"].ALPHANUM_HIDE_INPUT = 2

        class File:
            def __init__(self, p, mode="r"): self.f = open(p, "w" if mode == "w" else "r")
            def read(self): return self.f.read()
            def write(self, t): self.f.write(t)
            def close(self): self.f.close()
        sys.modules["xbmcvfs"].File = File
        d.xbmcvfs.File = File
        d.xbmcvfs.delete = os.remove
        d.log = lambda m: None
        d.toast = lambda m, ms=0: None
        self.path = d.data_file("phone.json")

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def raw(self):
        with open(self.path) as f:
            return f.read()

    def dlg(self, *typed, yes=True):
        typed = list(typed)
        test = self

        class D:
            said = []
            def ok(self, h, m): self.said.append(m)
            def input(self, h, *a, **k): return typed.pop(0) if typed else ""
            def yesno(self, h, m, **k): return yes
        return D()

    def test_without_a_passcode_nothing_changes(self):
        self.d.save_cache(self.path, {"dav": {"pass": "pw"}})
        self.assertIn("pw", self.raw())

    def test_turning_it_on_encrypts_existing_secrets_and_keeps_them_readable(self):
        self.d.save_cache(self.path, {"dav": {"pass": "pw123"}})
        self.d.vault_menu(self.dlg("1234", "1234"))
        self.assertNotIn("pw123", self.raw())
        self.assertEqual(self.d.load_cache(self.path)["dav"]["pass"], "pw123")
        self.d.save_cache(self.path, {"dav": {"pass": "new456"}})
        self.assertNotIn("new456", self.raw())
        self.assertEqual(self.d.load_cache(self.path)["dav"]["pass"], "new456")

    def test_mismatched_passcodes_change_nothing(self):
        self.d.save_cache(self.path, {"dav": {"pass": "pw123"}})
        self.d.vault_menu(self.dlg("1234", "5678"))
        self.assertIn("pw123", self.raw())

    def test_locked_means_empty_and_never_written_in_the_clear(self):
        self.d.save_cache(self.path, {"dav": {"pass": "pw123"}})
        self.d.vault_menu(self.dlg("1234", "1234"))
        self.props.clear()  # Kodi restarted
        before = self.raw()
        self.assertEqual(self.d.load_cache(self.path), {})
        self.assertFalse(self.d.save_cache(self.path, {"dav": {"pass": "overwrite"}}))
        self.assertEqual(self.raw(), before)

    def test_unlocking(self):
        self.d.save_cache(self.path, {"dav": {"pass": "pw123"}})
        self.d.vault_menu(self.dlg("1234", "1234"))
        self.props.clear()
        self.assertTrue(self.d.vault_unlock(self.dlg("1234")))
        self.assertEqual(self.d.load_cache(self.path)["dav"]["pass"], "pw123")

    def test_cancelling_the_passcode_stays_locked(self):
        self.d.vault_menu(self.dlg("1234", "1234"))
        self.props.clear()
        self.assertFalse(self.d.vault_unlock(self.dlg("")))

    def test_forgotten_passcode_erases_only_the_secrets(self):
        self.d.save_cache(self.path, {"dav": {"pass": "pw123"}})
        other = self.d.data_file("last_settings.json")
        self.d.save_cache(other, {"dest": "E"})
        self.d.vault_menu(self.dlg("1234", "1234"))
        self.props.clear()
        self.assertTrue(self.d.vault_unlock(self.dlg("wrong", yes=True)))
        self.assertFalse(os.path.exists(self.path))
        self.assertEqual(self.d.load_cache(other), {"dest": "E"})
        self.assertTrue(self.d.save_cache(self.path, {"dav": {"pass": "again"}}))
        self.assertIn("again", self.raw())

    def test_turning_it_off_restores_plain_files(self):
        self.d.save_cache(self.path, {"dav": {"pass": "pw123"}})
        self.d.vault_menu(self.dlg("1234", "1234"))
        self.d.vault_menu(self.dlg(yes=True))
        self.assertIn("pw123", self.raw())
        self.assertEqual(self.props.get(self.d.PROP_VAULT, ""), "")


if __name__ == "__main__":
    unittest.main()
