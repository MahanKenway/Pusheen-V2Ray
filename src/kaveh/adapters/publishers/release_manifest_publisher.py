"""Versioned, integrity-verifiable release manifests for public feed artifacts."""

from __future__ import annotations

import base64
import hashlib
import json
from dataclasses import dataclass
from datetime import UTC, datetime
from os import getenv
from typing import Iterable

from kaveh.domain.ports import ArtifactStore


@dataclass(frozen=True)
class ReleaseManifestPublishReport:
    published: bool
    release_id: str | None
    artifact_hash: str | None = None
    reason: str | None = None


class ReleaseManifestPublisher:
    """Publish an immutable integrity manifest and a small current-release pointer.

    The manifest publishes only paths, byte lengths, and SHA-256 hashes. It never
    reserializes or logs URI-bearing feed content. A signature is emitted only
    when the deployment supplies an Ed25519 private key through
    ``KAVEH_RELEASE_SIGNING_KEY``; unsigned operation stays explicit rather than
    presenting a generated key as durable provenance.
    """

    schema_version = 2
    manifest_prefix = "releases"
    current_pointer_path = "releases/current-release.json"
    signing_key_env = "KAVEH_RELEASE_SIGNING_KEY"
    artifact_paths = (
        "subscriptions/outage.txt",
        "subscriptions/outage.receipts.v1.json",
        "subscriptions/outage.manifest.v1.json",
        "subscriptions/resilient.txt",
        "subscriptions/resilient.receipts.v1.json",
        "profiles/resilient-xray.json",
        "profiles/resilient-xray.meta.v1.json",
        "profiles/outage-singbox.json",
        "profiles/outage-singbox.meta.v1.json",
        "status.json",
    )

    def __init__(self, artifact_store: ArtifactStore, signing_key: str | None = None) -> None:
        self.artifact_store = artifact_store
        self.signing_key = signing_key if signing_key is not None else getenv(self.signing_key_env)

    def publish(self, artifact_paths: Iterable[str] | None = None) -> ReleaseManifestPublishReport:
        read_bytes = getattr(self.artifact_store, "read_bytes", None)
        if not callable(read_bytes):
            return ReleaseManifestPublishReport(False, None, reason="ARTIFACT_STORE_NOT_READABLE")
        paths = tuple(artifact_paths or self.artifact_paths)
        artifacts: list[dict[str, object]] = []
        for path in paths:
            content = read_bytes(path)
            if not content:
                return ReleaseManifestPublishReport(False, None, reason=f"REQUIRED_ARTIFACT_MISSING:{path}")
            artifacts.append(
                {
                    "path": path,
                    "sha256": hashlib.sha256(content).hexdigest(),
                    "byte_length": len(content),
                }
            )
        artifacts.sort(key=lambda item: str(item["path"]))
        digest_input = "\n".join(f"{item['path']}:{item['sha256']}" for item in artifacts).encode("utf-8")
        release_digest = hashlib.sha256(digest_input).hexdigest()
        release_id = f"{datetime.now(UTC).strftime('%Y%m%dT%H%M%SZ')}-{release_digest[:12]}"
        unsigned = {
            "schema_version": self.schema_version,
            "release_id": release_id,
            "created_at": datetime.now(UTC).isoformat(),
            "integrity": {
                "algorithm": "sha256",
                "release_digest": release_digest,
                "signature_algorithm": "ed25519" if self.signing_key else None,
                "signature": None,
                "public_key": None,
            },
            "artifacts": artifacts,
            "notice": (
                "Hashes identify a publication set; they do not disclose endpoint hosts, "
                "credentials, or guarantee availability from another network."
            ),
        }
        signature, public_key = self._sign(unsigned)
        document = {
            **unsigned,
            "integrity": {
                **dict(unsigned["integrity"]),
                "signature": signature,
                "public_key": public_key,
            },
        }
        content = (json.dumps(document, sort_keys=True, indent=2) + "\n").encode("utf-8")
        artifact_hash = hashlib.sha256(content).hexdigest()
        manifest_path = f"{self.manifest_prefix}/{release_id}/manifest.v2.json"
        self.artifact_store.write_atomic(manifest_path, content)
        pointer = {
            "schema_version": self.schema_version,
            "release_id": release_id,
            "manifest_path": manifest_path,
            "manifest_sha256": artifact_hash,
            "signature_present": signature is not None,
            "updated_at": document["created_at"],
        }
        pointer_bytes = (json.dumps(pointer, sort_keys=True, indent=2) + "\n").encode("utf-8")
        existing = read_bytes(self.current_pointer_path)
        self.artifact_store.write_atomic(self.current_pointer_path, pointer_bytes)
        return ReleaseManifestPublishReport(
            existing != pointer_bytes,
            release_id,
            artifact_hash=artifact_hash,
            reason=None if existing != pointer_bytes else "NO_RELEASE_POINTER_CHANGE",
        )

    def _sign(self, unsigned_document: dict[str, object]) -> tuple[str | None, str | None]:
        if not self.signing_key:
            return None, None
        try:
            from cryptography.hazmat.primitives import serialization
            from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

            key = serialization.load_pem_private_key(
                self.signing_key.encode("utf-8"), password=None
            )
            if not isinstance(key, Ed25519PrivateKey):
                raise ValueError("release signing key must be Ed25519")
            payload = _canonical_signature_payload(unsigned_document)
            signature = key.sign(payload)
            public_key = key.public_key().public_bytes(
                serialization.Encoding.Raw, serialization.PublicFormat.Raw
            )
            return (
                base64.urlsafe_b64encode(signature).decode("ascii").rstrip("="),
                base64.urlsafe_b64encode(public_key).decode("ascii").rstrip("="),
            )
        except (ImportError, TypeError, ValueError) as exc:
            raise ValueError("RELEASE_SIGNING_KEY_INVALID") from exc


def _canonical_signature_payload(document: dict[str, object]) -> bytes:
    """Return the stable unsigned document representation used for verification."""

    return json.dumps(document, sort_keys=True, separators=(",", ":")).encode("utf-8")
