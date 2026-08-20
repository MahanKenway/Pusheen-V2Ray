from __future__ import annotations

import base64
import json
import tempfile
import unittest
from pathlib import Path

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey

from kaveh.adapters.publishers.release_manifest_publisher import (
    ReleaseManifestPublisher,
    _canonical_signature_payload,
)
from kaveh.infrastructure.storage.filesystem_store import FileSystemArtifactStore


class ReleaseManifestPublisherTests(unittest.TestCase):
    def _populate_required_artifacts(self, store: FileSystemArtifactStore) -> None:
        for index, path in enumerate(ReleaseManifestPublisher.artifact_paths):
            store.write_atomic(path, f"artifact-{index}\n".encode("utf-8"))

    def test_publishes_versioned_manifest_and_current_pointer_without_signing_key(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            store = FileSystemArtifactStore(Path(temporary))
            self._populate_required_artifacts(store)
            report = ReleaseManifestPublisher(store, signing_key="").publish()
            self.assertTrue(report.published)
            self.assertIsNotNone(report.release_id)
            pointer = json.loads(store.read_bytes("releases/current-release.json") or b"{}")
            self.assertFalse(pointer["signature_present"])
            manifest = json.loads(store.read_bytes(pointer["manifest_path"]) or b"{}")
            self.assertEqual(manifest["schema_version"], 2)
            self.assertEqual(manifest["release_id"], report.release_id)
            self.assertEqual(len(manifest["artifacts"]), len(ReleaseManifestPublisher.artifact_paths))
            self.assertNotIn("artifact-0", json.dumps(manifest))

    def test_signs_canonical_manifest_when_ed25519_key_is_supplied(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            store = FileSystemArtifactStore(Path(temporary))
            self._populate_required_artifacts(store)
            private_key = Ed25519PrivateKey.generate()
            private_pem = private_key.private_bytes(
                serialization.Encoding.PEM,
                serialization.PrivateFormat.PKCS8,
                serialization.NoEncryption(),
            ).decode("utf-8")
            report = ReleaseManifestPublisher(store, signing_key=private_pem).publish()
            pointer = json.loads(store.read_bytes("releases/current-release.json") or b"{}")
            manifest = json.loads(store.read_bytes(pointer["manifest_path"]) or b"{}")
            integrity = manifest["integrity"]
            self.assertTrue(pointer["signature_present"])
            self.assertEqual(integrity["signature_algorithm"], "ed25519")
            signature = base64.urlsafe_b64decode(integrity["signature"] + "==")
            public_bytes = base64.urlsafe_b64decode(integrity["public_key"] + "==")
            unsigned = dict(manifest)
            unsigned["integrity"] = dict(integrity)
            unsigned["integrity"]["signature"] = None
            unsigned["integrity"]["public_key"] = None
            Ed25519PublicKey.from_public_bytes(public_bytes).verify(
                signature, _canonical_signature_payload(unsigned)
            )
            self.assertEqual(report.release_id, manifest["release_id"])


if __name__ == "__main__":
    unittest.main()
