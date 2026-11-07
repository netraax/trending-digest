import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from bs4 import BeautifulSoup
import builder_profile
import business_digest
import business_template
import digest
from project_analysis import details_text, evidence_status


class ProfileTrustTests(unittest.TestCase):
    def test_all_profile_sections_survive_prompt_compaction(self):
        with patch.dict(os.environ, {"PROFILE_PATH": str(Path(__file__).with_name("profile.yml"))}):
            profile = builder_profile.load_profile()
        text = builder_profile.profile_context(profile)
        compact = json.loads(text)
        self.assertLessEqual(len(text.encode()), 2400)
        self.assertEqual(set(profile), set(compact))
        for section in profile:
            self.assertEqual(set(profile[section]), set(compact[section]))
        self.assertIn("disqualified_sectors", compact["strategic_focus"])
        self.assertIn("regional_advantage", compact["monetization_targets"])

    def test_invalid_or_missing_profile_never_silently_disappears(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder, "profile.yml")
            with patch.dict(os.environ, {"PROFILE_PATH": str(path)}):
                with self.assertRaises(RuntimeError):
                    builder_profile.load_profile()
                path.write_text("builder: [", encoding="utf-8")
                with self.assertRaises(RuntimeError):
                    builder_profile.load_profile()
                path.write_text("builder: {}", encoding="utf-8")
                with self.assertRaises(ValueError):
                    builder_profile.load_profile()

    def test_docker_includes_and_validates_profile(self):
        docker = Path(__file__).with_name("Dockerfile").read_text()
        self.assertIn("COPY profile.yml .", docker)
        self.assertIn("from builder_profile import load_profile; load_profile()", docker)

    def test_estimated_growth_is_not_reported_as_measured(self):
        item = dict(name="a/b", stars=100, stars_per_day=40, velocity_source="estimée")
        text = BeautifulSoup(business_template.render_html([item]), "html.parser").get_text()
        self.assertIn("Indice estimé", text)
        self.assertIn("pas une croissance récente mesurée", text)
        self.assertNotIn("FULGURANT", text)
        self.assertNotIn("Variation mesurée", text)

    def test_negative_star_changes_are_preserved(self):
        state = {"repos": {"a/b": {"history": [["2026-11-01", 100]]}}}
        candidate = {"name": "a/b", "stars": 90}
        business_digest.update_history(state, candidate, "2026-11-03")
        self.assertEqual(candidate["delta_per_day"], -5)

    def test_preview_has_no_fabricated_assessment(self):
        candidate = business_digest.fill_defaults({"name": "a/b", "description": "Un outil"})
        self.assertIsNone(candidate["score"])
        text = BeautifulSoup(business_template.render_html([candidate]), "html.parser").get_text()
        self.assertIn("Non évalué", text)
        self.assertIn("aucun extrait consulté", text)
        self.assertNotIn("5/10", text)
        self.assertNotIn("Océan bleu", text)
        self.assertNotIn("semaines", text)

    def test_no_llm_cannot_send_either_email(self):
        for module in (business_digest, digest):
            with patch("sys.argv", ["digest", "--no-llm"]), patch.object(module, "send_email") as send:
                with self.assertRaises(SystemExit):
                    module.main()
                send.assert_not_called()

    def test_evidence_label_matches_material_actually_read(self):
        self.assertIn("métadonnées seules", evidence_status({}))
        repo = {"evidence": {"sources": [{"kind": "documentation auteur"}]}}
        self.assertIn("documentation ou dépendances seulement", evidence_status(repo))
        repo["evidence"]["sources"][0]["kind"] = "extrait technique non exécuté"
        self.assertIn("lecture partielle", evidence_status(repo))
        self.assertIn("profil non évaluée", details_text({}))


if __name__ == "__main__":
    unittest.main()
