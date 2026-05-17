import unittest

from fastapi.testclient import TestClient

from app.main import app


class AppRoutesTests(unittest.TestCase):
    def test_root_health_and_docs_are_available(self) -> None:
        with TestClient(app) as client:
            root = client.get("/")
            health = client.get("/health")
            docs = client.get("/docs")

        self.assertEqual(root.status_code, 200)
        self.assertEqual(root.json()["docs_url"], "/docs")
        self.assertEqual(health.status_code, 200)
        self.assertEqual(health.json(), {"status": "ok"})
        self.assertEqual(docs.status_code, 200)


if __name__ == "__main__":
    unittest.main()
