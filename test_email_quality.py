import unittest
from project_analysis import field_text, quality_issues
from email_layout import check_size
from chatgpt_export import make_message


class EmailQualityTests(unittest.TestCase):
    def test_nested_json_and_jsonl(self):
        self.assertEqual(field_text('"{\\"actor\\": \\"Alice\\"}"'), "Utilisateur : Alice")
        result = field_text('{"actor":"A"}\n{"result":"B"}')
        self.assertIn("Utilisateur : A", result)
        self.assertIn("Résultat : B", result)
        self.assertNotIn("{", result)
        self.assertNotIn("{", field_text('{"broken":'))

    def test_claim_requires_matching_cited_excerpt(self):
        row = {"summary": "Réduit le délai de 70% [S1]."}
        self.assertTrue(quality_issues(row, []))
        self.assertFalse(quality_issues(row, [{"id": "S1", "excerpt": "70%"}]))
        self.assertFalse(quality_issues({"summary": "Objectif à tester : réduire de 70%."}, []))

    def test_inconsistent_workload_and_free_cost(self):
        self.assertTrue(quality_issues({"build_plan": "80 heures sur 4–6 semaines à 8–10h/jour"}, []))
        self.assertTrue(quality_issues({"build_plan": "Produit à 0€ avec Groq gratuit"}, []))
        self.assertFalse(quality_issues({"build_plan": "Coût à vérifier selon les quotas Groq gratuits"}, []))

    def test_html_size_including_copy_panel(self):
        with self.assertRaises(ValueError):
            check_size("é" * 45001)
        with self.assertRaises(ValueError):
            make_message("test", "a", "b", "a" * 89999, "texte")
