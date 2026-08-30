import shutil
import subprocess
import sys
import unittest
import uuid
from pathlib import Path

from pypdf import PdfWriter


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "verify_pdf_layout.py"


class VerifyPdfLayoutTests(unittest.TestCase):
    def setUp(self):
        root = ROOT / ".test-tmp"
        root.mkdir(exist_ok=True)
        self.directory = root / f"pdf-{uuid.uuid4().hex}"
        self.directory.mkdir()

    def tearDown(self):
        shutil.rmtree(self.directory, ignore_errors=True)

    def make_pdf(self, pages):
        path = self.directory / f"{pages}-pages.pdf"
        writer = PdfWriter()
        for _ in range(pages):
            writer.add_blank_page(width=612, height=792)
        with path.open("wb") as stream:
            writer.write(stream)
        return path

    def run_check(self, pages):
        return subprocess.run(
            [sys.executable, str(SCRIPT), str(self.make_pdf(pages)), "--expected-pages", "1"],
            capture_output=True, text=True, check=False)

    def test_one_page_pdf_passes(self):
        result = self.run_check(1)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('"page_count": 1', result.stdout)

    def test_two_page_pdf_is_blocked(self):
        result = self.run_check(2)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("expected 1", result.stderr.lower())


if __name__ == "__main__":
    unittest.main()
