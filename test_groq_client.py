"""Offline regression tests. No real Groq, GitHub or SMTP calls."""
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch

import business_digest
import digest
import project_analysis
from groq_client import GroqClient, SmallerBatchNeeded, duration


class GroqTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        env = patch.dict(os.environ, {"LOG_DIR": self.directory.name,
                         "GROQ_MODEL": "openai/gpt-oss-120b",
                         "GROQ_DAILY_TOKEN_BUDGET": "180000",
                         "GROQ_DAILY_REQUEST_BUDGET": "900",
                         "GROQ_REQUEST_TOKEN_LIMIT": "7000",
                         "GROQ_MAX_WAIT_SECONDS": "1800"})
        env.start()
        self.addCleanup(env.stop)
        self.clock = 1000000.0
        p = patch("groq_client.time.time", side_effect=lambda: self.clock)
        p.start()
        self.addCleanup(p.stop)
        p = patch("groq_client.time.sleep", side_effect=self.advance)
        p.start()
        self.addCleanup(p.stop)
        p = patch("groq_client.requests.post", side_effect=self.reply)
        self.post = p.start()
        self.addCleanup(p.stop)

    def advance(self, seconds):
        self.clock += seconds

    def reply(self, *args, **kwargs):
        prompt = kwargs["json"]["messages"][0]["content"]
        items = json.loads(prompt.rsplit("\n\n", 1)[1])
        field = "projects" if '"projects"' in prompt else ("opportunities" if "opportunities" in prompt else "repos")
        rows = [dict(name=i["name"], eli5="Explication", category="Outil",
                     business_idea="Idée", problem="Problème", code_mechanism="Mécanisme",
                     target="Client", idea="Produit", score=7, fit_score=8) for i in items]
        if field == "projects":
            for row in rows:
                row.update({k: "Explication" for k in project_analysis.FIELDS})
                row.update(eligible=True, evidence_ids=[])
        return self.response({field: rows})

    @staticmethod
    def response(data, status=200, headers=None, finish="stop"):
        return Mock(status_code=status, ok=status == 200, headers=headers or {}, text="error",
                    json=Mock(return_value={"choices": [{"finish_reason": finish,
                              "message": {"content": json.dumps(data)}}],
                              "usage": {"total_tokens": 200, "prompt_tokens": 150,
                                        "completion_tokens": 50}}))

    @staticmethod
    def items(count):
        return [{"name": f"owner/repo{i}"} for i in range(count)]

    def test_batch_order_spacing_and_cache_across_restarts(self):
        items = self.items(10)
        rows, model = GroqClient("secret", "trending").analyze("repos", items, "repos", require_all=True)
        self.assertEqual([r["name"] for r in rows], [r["name"] for r in items])
        self.assertEqual(self.post.call_count, 5)
        self.assertGreaterEqual(self.clock, 1000000 + 4 * 65)
        GroqClient("secret", "trending").analyze("repos", items, "repos", require_all=True)
        self.assertEqual(self.post.call_count, 5)
        state = Path(self.directory.name, "groq_runtime.json").read_text()
        self.assertNotIn("secret", state)
        self.assertEqual(sum(c["tokens"] for c in json.loads(state)["calls"]), 1000)

    def test_429_honors_server_wait(self):
        self.post.side_effect = [self.response({}, 429, {"retry-after": "125"}),
                                 self.response({"repos": self.items(1)})]
        GroqClient("secret", "trending").analyze("repos", self.items(1), "repos", require_all=True)
        self.assertEqual(self.post.call_count, 2)
        self.assertGreaterEqual(self.clock, 1000125)

    def test_oversized_tpm_429_requests_smaller_context_immediately(self):
        payload = {"error": {"message": "Request too large: Requested 8998 tokens, limit 8000 TPM"}}
        response = Mock(status_code=429, ok=False, headers={}, text=json.dumps(payload),
                        json=Mock(return_value=payload))
        self.post.side_effect = None
        self.post.return_value = response

        with self.assertRaisesRegex(SmallerBatchNeeded, "Requested 8998"):
            GroqClient("secret", "business").call("short prompt", 100, lambda _: True)
        self.assertEqual(self.post.call_count, 1)

    def test_retry_exhaustion_reports_provider_status(self):
        self.post.side_effect = [self.response({}, 503)] * 5
        with self.assertRaisesRegex(RuntimeError, "HTTP 503"):
            GroqClient("secret", "business").call("short prompt", 100, lambda _: True)
        self.assertEqual(self.post.call_count, 5)

    def test_transient_failure_moves_to_fallback_model(self):
        self.post.side_effect = [self.response({}, 503)] * 5 + [
            self.response({"repos": self.items(1)})
        ]
        client = GroqClient("secret", "business")
        client.models = ["model-a", "model-b"]
        rows, model = client.analyze("repos", self.items(1), "repos", require_all=True)
        self.assertEqual(rows[0]["name"], "owner/repo0")
        self.assertEqual(model, "model-b")

    def test_daily_limit_is_shared_between_emails(self):
        GroqClient("secret", "trending").analyze("repos", self.items(1), "repos")
        with patch.dict(os.environ, {"GROQ_DAILY_TOKEN_BUDGET": "300"}):
            with self.assertRaisesRegex(RuntimeError, "partagé"):
                GroqClient("secret", "business").analyze("opportunities", self.items(1), "opportunities")
        self.assertEqual(self.post.call_count, 1)

    def test_413_splits_without_dropping_items(self):
        attempts = []

        def reply(*args, **kwargs):
            attempts.append(1)
            return self.response({}, 413) if len(attempts) == 1 else self.reply(*args, **kwargs)

        self.post.side_effect = reply
        rows, _ = GroqClient("secret", "trending").analyze("repos", self.items(2), "repos", require_all=True)
        self.assertEqual(len(rows), 2)
        self.assertEqual(self.post.call_count, 3)

    def test_truncation_splits_and_missing_names_retry(self):
        self.post.side_effect = [self.response({}, finish="length"),
                                 self.response({"repos": []}),
                                 self.response({"repos": self.items(1)}),
                                 self.response({"repos": [{"name": "owner/repo1"}]})]
        rows, _ = GroqClient("secret", "trending").analyze("repos", self.items(2), "repos", require_all=True)
        self.assertEqual(len(rows), 2)
        self.assertEqual(self.post.call_count, 4)

    def test_completed_batch_survives_later_failure(self):
        self.post.side_effect = [self.response({"repos": self.items(2)})] + [self.response({}, 503)] * 5
        with self.assertRaises(RuntimeError):
            GroqClient("secret", "trending").analyze("repos", self.items(4), "repos", require_all=True)
        self.post.side_effect = self.reply
        rows, _ = GroqClient("secret", "trending").analyze("repos", self.items(4), "repos", require_all=True)
        self.assertEqual(len(rows), 4)
        self.assertEqual(self.post.call_count, 7)  # only the unfinished batch is retried

    def test_excessive_server_wait_stops_without_email_or_lost_cache(self):
        self.post.return_value = self.response({}, 429, {"retry-after": "86400"})
        self.post.side_effect = None
        with self.assertRaisesRegex(RuntimeError, "reprise nécessaire"):
            GroqClient("secret", "business").analyze("opportunities", self.items(1), "opportunities")
        self.assertEqual(self.post.call_count, 1)

    def test_oversized_single_item_fails_before_network(self):
        with self.assertRaisesRegex(SmallerBatchNeeded, "budget"):
            GroqClient("secret", "trending").analyze("repos", [{"name": "x", "text": "x" * 20000}], "repos")
        self.post.assert_not_called()

    def test_daily_integration_keeps_ten(self):
        repos = [dict(i, description="Description", language="Python") for i in self.items(10)]
        with patch.object(project_analysis, "collect_evidence", return_value={"sources": [], "notes": []}):
            digest.explain(repos, "secret")
        self.assertEqual(len(repos), 10)
        self.assertTrue(all(r["eli5"] == "Explication" for r in repos))
        self.assertEqual(self.post.call_count, 10)

    def test_business_analyzes_fifteen_and_selects_six(self):
        candidates = [dict(i, description="Description", language="Python", topics=[], stars=30,
                          forks=3, open_issues=1, age_days=4, stars_per_day=3,
                          license="MIT", owner_type="User", homepage="", monetized_hints=[])
                      for i in self.items(15)]
        with patch.object(project_analysis, "collect_evidence", return_value={"sources": [], "notes": []}), \
             patch.object(business_digest, "fetch_user_feedback", return_value={}):
            rows, _ = business_digest.analyze_business_opportunities(candidates, "secret")
        self.assertEqual(len(rows), 6)
        self.assertEqual(self.post.call_count, 15)

    def test_duration_headers(self):
        self.assertEqual(duration("1m2.5s"), 62.5)
        self.assertEqual(duration("250ms"), .25)


if __name__ == "__main__":
    unittest.main()
