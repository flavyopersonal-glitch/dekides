import unittest
from pathlib import Path
from packaging.requirements import Requirement
from app.render_start import commands

class Render(unittest.TestCase):
    def test_requisitos_instalaveis(self):
        requirements = [Requirement(s) for s in Path("requirements.txt").read_text().splitlines() if s.strip()]
        self.assertIn("requests", [r.name for r in requirements])
        self.assertIn("email-validator", [r.name for r in requirements])

    def test_porta_render(self):
        api,ui,env=commands({"PORT":"12345"})
        self.assertIn("127.0.0.1",api)
        self.assertIn("--server.port=12345",ui)
        self.assertEqual(env["DEKIDS_API_URL"],"http://127.0.0.1:8000")

    def test_portas_distintas(self):
        api,ui,env=commands({"PORT":"8000"})
        self.assertEqual(env["DEKIDS_API_URL"],"http://127.0.0.1:8001")
        self.assertIn("--server.port=8000",ui)
