import sys
import unittest
from pathlib import Path


BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

import main  # noqa: E402


class CorsConfigTests(unittest.TestCase):
    def test_default_origins_allow_vite_on_localhost_and_loopback_ip(self):
        self.assertIn("http://localhost:5173", main.allowed_origins)
        self.assertIn("http://127.0.0.1:5173", main.allowed_origins)


if __name__ == "__main__":
    unittest.main()
