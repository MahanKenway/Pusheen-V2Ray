from __future__ import annotations

import os
import unittest

from kaveh.adapters.protocols.registry import ParserRegistry
from kaveh.domain.models import ProbeResult, ProbeStage, Source
from kaveh.domain.services.qualification import QualificationPolicy
from kaveh.infrastructure.persistence.postgres import (
    PostgresConfigRepository,
    PostgresDatabase,
    PostgresValidationHistory,
)


@unittest.skipUnless(os.getenv("KAVEH_TEST_DATABASE_URL"), "KAVEH_TEST_DATABASE_URL is not configured")
class PostgresPersistenceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.database = PostgresDatabase(os.environ["KAVEH_TEST_DATABASE_URL"])
        cls.database.migrate("migrations")

    def setUp(self) -> None:
        with self.database.transaction() as connection:
            connection.execute(
                """
                TRUNCATE TABLE publication_snapshots, scorecards, probe_results,
                validation_runs, config_status, config_observations, configs, sources
                RESTART IDENTITY CASCADE
                """
            )

    def test_config_history_and_status_are_persisted(self) -> None:
        source = Source("fixture", "https://example.com/sub", trust_weight=0.8)
        config = ParserRegistry().parse(
            "trojan://secret@example.com:443?security=tls#fixture",
            source_id=source.source_id,
        )
        configs = PostgresConfigRepository(self.database)
        configs.upsert_source(source)
        self.assertTrue(configs.upsert(config))
        self.assertFalse(configs.upsert(config))
        self.assertEqual(configs.get(config.identity_hash or "").identity_hash, config.identity_hash)

        history = PostgresValidationHistory(self.database)
        history.start_run("kaveh-standard-v1", "local-test")
        history.append([ProbeResult.passed(config.identity_hash or "", ProbeStage.END_TO_END, 120)])
        health = history.health_window(config.identity_hash or "")
        card = QualificationPolicy().score(health, source.trust_weight)
        history.save_scorecard(card)
        history.finish_run()

        self.assertEqual(health.success_count, 1)
        self.assertTrue(card.qualified)
        with self.database.transaction() as connection:
            status = connection.execute(
                "SELECT state, score, last_e2e_success_at FROM config_status WHERE identity_hash = %s",
                (config.identity_hash,),
            ).fetchone()
        self.assertEqual(status["state"], "qualified")
        self.assertEqual(status["score"], card.score)
        self.assertIsNotNone(status["last_e2e_success_at"])


if __name__ == "__main__":
    unittest.main()
