import base64
import json
import unittest
from unittest.mock import Mock, patch

from bs4 import BeautifulSoup
import project_analysis as analysis
import email_template
import business_template
from groq_client import estimate_tokens


class EvidenceTests(unittest.TestCase):
    def test_readme_selects_usage_after_long_intro(self):
        text = "# Tool\n" + "marketing " * 1000 + "\n## Usage\nconvert input.pdf output.json"
        self.assertIn("convert input.pdf", analysis.excerpts(text))

    def test_pinned_sources_and_decoding(self):
        paths = ["README.md", "pyproject.toml", "examples/demo.py"]
        payloads = [{"sha": "abc123"}, {"tree": [dict(path=p, type="blob", size=100) for p in paths]}]
        payloads += [{"encoding": "base64", "content": base64.b64encode(f"Example {p}".encode()).decode()} for p in paths]
        with patch.object(analysis.requests, "get", side_effect=[Mock(ok=True, json=Mock(return_value=p)) for p in payloads]) as get:
            result = analysis.collect_evidence("owner/repo")
        self.assertEqual(len(result["sources"]), 3)
        self.assertTrue(all("/blob/abc123/" in s["url"] for s in result["sources"]))
        self.assertEqual(get.call_args.kwargs["params"], {"ref": "abc123"})
        self.assertEqual(result["sources"][2]["kind"], "extrait technique non exécuté")

    def test_unavailable_repo_is_explicit(self):
        with patch.object(analysis.requests, "get", return_value=Mock(ok=False, status_code=403)):
            result = analysis.collect_evidence("owner/repo")
        self.assertEqual(result["sources"], [])
        self.assertIn("HTTP 403", result["notes"][0])

    def test_context_is_bounded_with_profile(self):
        evidence = {"sources": [dict(id="S1", excerpt="é" * 20000, path="README.md", kind="doc", url="https://github.com/a/b")], "notes": []}
        row = dict(name="a/b", eligible=True, score=7, fit_score=7, evidence_ids=["S1"],
                   **{key: "Exemple [S1]" for key in analysis.FIELDS})
        client = Mock(request_limit=7000)

        def analyze(prompt, items, field, **kwargs):
            self.assertLessEqual(estimate_tokens(prompt + "\n\n" + json.dumps(items, ensure_ascii=False)) + kwargs["output_tokens"], 7000)
            self.assertTrue(kwargs["row_validator"](row))
            self.assertFalse(kwargs["row_validator"](dict(row, evidence_ids=["S99"])))
            return [row], "test"

        client.analyze.side_effect = analyze
        with patch.object(analysis, "GroqClient", return_value=client), patch.object(analysis, "collect_evidence", return_value=evidence):
            analysis.analyze_projects([{"name": "a/b"}], "fake", "business", profile={"text": "p" * 5000})

    def test_both_html_templates_include_all_details_and_escape_content(self):
        repo = dict(name="a/b", url="https://github.com/a/b", language="Python", stars=100,
                    forks=3, gained_n=10, eli5="Description", score=7, fit_score=7,
                    evidence={"sources": [dict(id="S1", path="README.md", kind="doc", url="https://github.com/a/b/blob/abc/README.md")], "notes": []},
                    **{key: f"{key} <script>alert(1)</script>" for key in analysis.FIELDS})
        for output in (email_template.render_html([repo, repo], "daily"), business_template.render_html([repo], 15)):
            soup = BeautifulSoup(output, "html.parser")
            self.assertFalse(soup.find_all("script"))
            for _, label in analysis.LABELS:
                self.assertIn(label, soup.get_text())
            self.assertIn("code non exécuté", soup.get_text())
            self.assertTrue(soup.find("a", href=repo["evidence"]["sources"][0]["url"]))

        editorial = email_template.render_html([repo, repo], "daily")
        business = business_template.render_html([repo], 15)
        self.assertIn("background:#C6FF3D", editorial)
        self.assertIn("background:#DBEAFE", business)
        self.assertIn("PISTES DE PRODUIT", editorial)
        self.assertIn("CONSTRUIRE ET TESTER", business)


if __name__ == "__main__":
    unittest.main()
