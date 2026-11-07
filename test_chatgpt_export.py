from collections import Counter
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from bs4 import BeautifulSoup
import business_digest
from chatgpt_export import build_prompt, copy_page, email_content, make_message


class ExportTests(unittest.TestCase):
    def test_complete_content_links_and_instructions(self):
        body = '<html><head><style>hidden css</style></head><body><h1>6 projets</h1><p>★ 123</p><a href="https://github.com/a/b">Source</a><p>Dernier projet</p></body></html>'
        prompt = build_prompt("Radar", email_content(body))
        for text in ("6 projets", "123", "Dernier projet", "https://github.com/a/b", "TOP 3", "chiffre d'affaires"):
            self.assertIn(text, prompt)
        self.assertNotIn("hidden css", prompt)

    def test_untrusted_email_cannot_escape_textarea(self):
        text = '</textarea><script>alert("bad")</script> & é'
        soup = BeautifulSoup(copy_page(text), "html.parser")
        self.assertEqual(soup.find("textarea").get_text(), text)
        self.assertEqual(len(soup.find_all("script")), 1)
        self.assertIn("navigator.clipboard.writeText(area.value)", soup.find("script").text)
        self.assertIn("area.setSelectionRange", soup.find("script").text)

    def test_message_has_alternatives_and_equivalent_attachments(self):
        message = make_message("Radar", "sender@example.org", "reader@example.org", '<body><p>Contenu</p></body>', "Contenu")
        self.assertEqual(message.get_content_subtype(), "mixed")
        alternatives, page, plain = message.get_payload()
        self.assertEqual(alternatives.get_content_subtype(), "alternative")
        html_mail = alternatives.get_payload()[1].get_payload(decode=True).decode("utf-8")
        self.assertNotIn("<script", html_mail)
        self.assertIn("pièce jointe", html_mail)
        textarea = BeautifulSoup(page.get_payload(decode=True).decode("utf-8"), "html.parser").find("textarea").text
        self.assertEqual(textarea, plain.get_payload(decode=True).decode("utf-8"))
        self.assertEqual(page.get_filename(), "copier-pour-chatgpt.html")

    def test_daily_radar_also_sends_no_news_bulletin(self):
        with tempfile.TemporaryDirectory() as folder:
            with patch("sys.argv", ["radar", "--out", folder]), \
                 patch.object(business_digest, "LOG_DIR", folder), \
                 patch.object(business_digest, "load_state", return_value={"repos": {}}), \
                 patch.object(business_digest, "load_profile", return_value={}), \
                 patch.object(business_digest, "select_candidates", return_value=([], {}, Counter(), {})), \
                 patch.object(business_digest, "send_email", return_value="test") as send, \
                 patch.object(business_digest, "analyze_business_opportunities") as analyze:
                business_digest.main()
                send.assert_called_once()
                analyze.assert_not_called()
                self.assertIn("Aucun nouveau projet", send.call_args.args[1])
                self.assertTrue(Path(folder, "business_chatgpt.html").exists())

    def test_daily_guard(self):
        workflow = Path(__file__).with_name('.github').joinpath('workflows/business_digest.yml').read_text(encoding='utf-8')
        self.assertIn("diff >= 1", workflow)
        self.assertNotIn("diff >= 2", workflow)


if __name__ == "__main__":
    unittest.main()
