import os
import unittest
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient
from main import app
from services.legal_search import LegalChunk, search_legal_chunks
from services.serpapi_client import (
    SerpWebResult,
    formulate_legal_search_query,
    is_legal_web_candidate,
    legal_web_results_to_chunks,
    sanitize_query,
    search_legal_web,
    serpapi_enabled,
)


class SerpApiClientTests(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)

    def test_serpapi_enabled_detection(self):
        with patch.dict(os.environ, {"SERPAPI_API_KEY": "valid_key"}, clear=False):
            self.assertTrue(serpapi_enabled())
        with patch.dict(os.environ, {"SERPAPI_API_KEY": ""}, clear=False):
            self.assertFalse(serpapi_enabled())

    def test_sanitize_query_removes_pii(self):
        raw = "My husband Ramesh beat me at Flat 402 Pune, call me at 9876543210 or user@test.com"
        sanitized = sanitize_query(raw)
        self.assertNotIn("9876543210", sanitized)
        self.assertNotIn("user@test.com", sanitized)
        self.assertNotIn("Flat 402", sanitized)
        self.assertNotIn("Ramesh", sanitized)
        self.assertIn("Pune", sanitized)
        self.assertIn("domestic violence", sanitized.lower())

    def test_is_legal_web_candidate(self):
        # Institutional queries
        self.assertTrue(is_legal_web_candidate("Where is the DLSA office in Pune?"))
        self.assertTrue(is_legal_web_candidate("Who is the Protection Officer in South Delhi?"))
        self.assertTrue(is_legal_web_candidate("How to contact Sakhi One Stop Centre in Jaipur?"))
        self.assertTrue(is_legal_web_candidate("How can I find legal aid in Lucknow?"))

        # Purely statutory questions should NOT trigger web candidate
        self.assertFalse(is_legal_web_candidate("What is Section 18 of Domestic Violence Act?"))
        self.assertFalse(is_legal_web_candidate("Explain private defence under BNS"))
        self.assertFalse(is_legal_web_candidate("What is a protection order?"))

    def test_formulate_legal_search_query(self):
        formulated = formulate_legal_search_query("Who is the protection officer in Pune?")
        self.assertIn("Protection Officer", formulated)
        self.assertIn("Pune", formulated)
        self.assertIn("India", formulated)

    def test_search_legal_web_disabled_returns_empty(self):
        with patch.dict(os.environ, {"SERPAPI_API_KEY": ""}, clear=False):
            results = search_legal_web("Where is DLSA Pune?")
            self.assertEqual(results, [])

    @patch("services.serpapi_client._fetch_from_serpapi")
    def test_search_legal_web_caching_and_mock(self, mock_fetch):
        mock_fetch.return_value = [
            SerpWebResult(
                title="District Legal Services Authority Pune",
                link="https://pune.dcourts.gov.in/dlsa",
                snippet="Official portal of DLSA Pune offering free legal aid.",
                source_name="pune.dcourts.gov.in",
            )
        ]
        with patch.dict(os.environ, {"SERPAPI_API_KEY": "dummy_key"}, clear=False):
            # First call
            res1 = search_legal_web("DLSA Pune portal", max_results=2)
            self.assertEqual(len(res1), 1)
            self.assertEqual(res1[0].title, "District Legal Services Authority Pune")
            self.assertEqual(mock_fetch.call_count, 1)

            # Second call should hit in-memory cache
            res2 = search_legal_web("DLSA Pune portal", max_results=2)
            self.assertEqual(len(res2), 1)
            self.assertEqual(mock_fetch.call_count, 1)

    def test_legal_web_results_to_chunks(self):
        web_results = [
            SerpWebResult(
                title="Maharashtra State Legal Services Authority",
                link="https://legalservices.maharashtra.gov.in/",
                snippet="Free legal aid, counsel, and assistance for women and marginalized persons.",
                source_name="legalservices.maharashtra.gov.in",
            )
        ]
        chunks = legal_web_results_to_chunks(web_results)
        self.assertEqual(len(chunks), 1)
        self.assertEqual(chunks[0].chunk_id, "serpapi-web-1")
        self.assertEqual(chunks[0].source_url, "https://legalservices.maharashtra.gov.in/")
        self.assertIn("Verified Live Official Web Source", chunks[0].status)
        self.assertGreaterEqual(chunks[0].score, 0.90)

    @patch("services.legal_search.serpapi_enabled", return_value=True)
    @patch("services.legal_search.search_legal_web")
    def test_search_legal_chunks_integrates_web_for_candidate(self, mock_web, _mock_enabled):
        mock_web.return_value = [
            SerpWebResult(
                title="DLSA Pune Contact & Office Details",
                link="https://pune.dcourts.gov.in/contact",
                snippet="Contact details and address of District Legal Services Authority Pune.",
                source_name="pune.dcourts.gov.in",
            )
        ]
        chunks, source = search_legal_chunks("Where can I find DLSA Pune office?")
        self.assertEqual(source, "serpapi-web")
        self.assertTrue(any(c.chunk_id.startswith("serpapi-web") for c in chunks))
        self.assertEqual(chunks[0].source_url, "https://pune.dcourts.gov.in/contact")

    @patch("routers.legal.search_legal_chunks")
    def test_legal_ask_endpoint_with_serpapi_web(self, mock_search):
        web_chunk = LegalChunk(
            chunk_id="serpapi-web-1",
            title="District Legal Services Authority Pune",
            section="Portal / Directory: pune.dcourts.gov.in",
            text="Official legal aid portal in Pune offering free legal aid counsel.",
            source="pune.dcourts.gov.in",
            source_url="https://pune.dcourts.gov.in/dlsa",
            score=0.92,
            status="Verified Live Official Web Source",
        )
        mock_search.return_value = ([web_chunk], "serpapi-web")

        response = self.client.post("/legal/ask", json={"question": "Where can I find DLSA Pune?"})
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data["in_scope"])
        self.assertEqual(data["retrieval_source"], "serpapi-web")
        self.assertGreater(len(data["citations"]), 0)
        self.assertEqual(data["citations"][0]["source_url"], "https://pune.dcourts.gov.in/dlsa")
        self.assertIn("[Source 1]", data["answer"])


if __name__ == "__main__":
    unittest.main()
