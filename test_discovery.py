from datetime import datetime, timezone
from collections import Counter
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import business_digest as radar


NOW = datetime(2026, 11, 7, tzinfo=timezone.utc)


def candidate(name="author/tool", **changes):
    c = dict(name=name, description="A useful automation tool", topics=[], stars=60, forks=2,
             age_days=5, push_age_days=1, owner=name.split("/")[0], language="Python",
             nets=["frais"], pushed_at="2026-11-06T00:00:00Z")
    c.update(changes)
    return c


class DiscoveryTests(unittest.TestCase):
    def test_existing_nets_preserved_with_bounded_exploration(self):
        queries = radar.build_queries(NOW)
        self.assertEqual([q[0] for q in queries[:5]], ["frais", "reveilles", "alternatives", "self-hosted", "saas"])
        self.assertEqual(sum(q[3] for q in queries), 8)
        self.assertTrue(all("size:" not in q[1] for q in queries))
        self.assertIn("stars:3..50", queries[5][1])
        self.assertIn("2026-10-08..2026-10-28", queries[6][1])

    def test_ambiguous_signals_do_not_exclude_real_tools(self):
        cases = [candidate("nvidia/tool", stars=900, forks=0, age_days=2),
                 candidate(description="", push_age_days=35),
                 candidate("user/portfolio-builder", description="Build portfolio websites"),
                 candidate("user/interview-tool", description="Transcribe customer interviews")]
        for c in cases:
            self.assertIsNone(radar.reject_reason(c))
            self.assertGreater(radar.pre_score(c), 0)
        self.assertNotIn("spam_arnaque", radar.candidate_signals(cases[0]))

    def test_only_structural_cases_are_excluded(self):
        for flag in ("fork", "archived", "disabled", "mirror"):
            self.assertEqual(radar.reject_reason(candidate(**{flag: True})), flag)

    def test_noise_is_downranked_not_silently_dropped(self):
        clean = candidate()
        noisy = candidate("user/homework", description="Homework tutorial assignment")
        self.assertLess(radar.pre_score(noisy), radar.pre_score(clean))
        self.assertIsNone(radar.reject_reason(noisy))

    def test_viral_growth_is_tempered_and_score_is_explainable(self):
        normal = candidate(delta_per_day=10)
        viral = candidate(delta_per_day=1000)
        self.assertLess(radar.pre_score(viral) / radar.pre_score(normal), 4)
        self.assertIn("facteur_prudence", viral["score_components"])
        self.assertEqual(viral["velocity_source"], "mesurée")

    def test_exploration_slots_and_unique_bounded_selection(self):
        pool = [candidate(f"owner{i}/tool", stars=500, pre_score=20-i/100) for i in range(20)]
        pool += [candidate(f"small{i}/tool", stars=8, pre_score=3) for i in range(4)]
        selected = radar.choose_shortlist(pool, 15)
        self.assertEqual(len(selected), 15)
        self.assertEqual(len({c["name"] for c in selected}), 15)
        self.assertEqual(sum(c["selection_reason"] == "exploration_projet_discret" for c in selected), 3)

    def test_diversity_is_soft_and_can_fill_from_one_owner(self):
        pool = [candidate(f"same/tool{i}", pre_score=10) for i in range(10)]
        pool.append(candidate("other/tool", pre_score=9))
        selected = radar.choose_shortlist(pool, 5)
        self.assertIn("other/tool", [c["name"] for c in selected[:2]])
        self.assertEqual(len(radar.choose_shortlist(pool[:4], 15)), 4)

    def test_reanalysis_on_growth_or_update_without_daily_repetition(self):
        c = candidate(stars=100, pushed_at="2026-11-06T00:00:00Z")
        rec = dict(analyzed_stars=100, analyzed_at="2026-11-01", last_seen="2026-11-07",
                   analyzed_push="2026-10-30T00:00:00Z")
        state = {"repos": {c["name"]: rec}}
        self.assertTrue(radar.already_handled(c, state))
        self.assertFalse(radar.already_handled(dict(c, stars=200), state))
        rec["last_seen"] = "2026-11-16"
        self.assertFalse(radar.already_handled(c, state))
        rec["analyzed_push"] = c["pushed_at"]
        self.assertTrue(radar.already_handled(c, state))
        rec["last_seen"] = "2026-12-02"
        self.assertFalse(radar.already_handled(c, state))

    def test_old_state_remains_compatible(self):
        c = candidate(stars=100)
        state = {"repos": {c["name"]: {"analyzed_stars": 90, "first_seen": "2026-11-06",
                                       "last_seen": "2026-11-07"}}}
        self.assertTrue(radar.already_handled(c, state))

    def test_observations_saved_before_model_failure(self):
        with tempfile.TemporaryDirectory() as folder:
            today = datetime.now(timezone.utc).date().isoformat()
            state = {"repos": {"a/b": {"history": [[today, 10]], "last_seen": today}}}
            with patch("sys.argv", ["radar", "--out", folder]), \
                 patch.object(radar, "LOG_DIR", folder), patch.object(radar, "load_state", return_value=state), \
                 patch.object(radar, "load_profile", return_value={}), \
                 patch.object(radar, "select_candidates", return_value=([candidate("a/b")], {}, Counter(), {})), \
                 patch.dict(radar.os.environ, {"GROQ_API_KEY": "fake"}), \
                 patch.object(radar, "analyze_business_opportunities", side_effect=RuntimeError("test failure")), \
                 patch.object(radar, "send_email") as send:
                with self.assertRaises(RuntimeError):
                    radar.main()
                saved = json.loads(Path(folder, "business_state.json").read_text())
                self.assertNotIn("last_sent", saved)
                self.assertEqual(saved["repos"]["a/b"]["history"], [[today, 10]])
                self.assertTrue(Path(folder, "discovery_report.json").exists())
                send.assert_not_called()


if __name__ == "__main__":
    unittest.main()
