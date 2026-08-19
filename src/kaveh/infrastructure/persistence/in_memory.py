"""In-memory repository for local development and deterministic tests."""

from __future__ import annotations

from kaveh.domain.models import CanonicalConfig


class InMemoryConfigRepository:
    """Identity-keyed repository implementing the domain repository port."""

    def __init__(self) -> None:
        self._configs: dict[str, CanonicalConfig] = {}

    def upsert(self, config: CanonicalConfig) -> bool:
        if not config.identity_hash:
            raise ValueError("CanonicalConfig must have an identity hash")
        is_new = config.identity_hash not in self._configs
        self._configs.setdefault(config.identity_hash, config)
        return is_new

    def get(self, identity_hash: str) -> CanonicalConfig | None:
        return self._configs.get(identity_hash)

    def all(self) -> tuple[CanonicalConfig, ...]:
        return tuple(self._configs.values())
