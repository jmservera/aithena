"""
Smoke tests for the Locust load-test helpers.

These tests validate the *task definitions and helper functions* in
``locustfile.py`` and ``test_concurrent.py`` **without** starting a Locust
runner or requiring the Aithena stack.  They are safe to run in any CI
environment.

Run::

    cd tests/stress
    python3 -m pytest test_locust_smoke.py -x -q --timeout=30
"""

from __future__ import annotations

from pathlib import Path

import pytest

# Import helpers from the locustfile (no Locust runner needed)
from locustfile import (
    FACET_AUTHORS,
    FACET_CATEGORIES,
    SCENARIOS,
    SEARCH_MODES,
    SEARCH_QUERIES,
    build_books_params,
    build_facet_params,
    build_search_params,
    choose_random_mode,
    choose_random_query,
    get_scenario,
    make_tiny_pdf,
    parse_search_response,
)
from test_concurrent import (
    SCENARIOS as CONCURRENT_SCENARIOS,
)
from test_concurrent import (
    LoadScenario,
    build_locust_command,
    check_pass_criteria,
    parse_locust_csv_stats,
    summarise_locust_run,
)

# ===================================================================
# locustfile.py — query / data pool tests
# ===================================================================


class TestSearchQueries:
    """Validate the shared query and data pools."""

    def test_query_pool_not_empty(self):
        assert len(SEARCH_QUERIES) > 0

    def test_queries_are_strings(self):
        for q in SEARCH_QUERIES:
            assert isinstance(q, str) and len(q) > 0

    def test_facet_authors_not_empty(self):
        assert len(FACET_AUTHORS) > 0

    def test_facet_categories_not_empty(self):
        assert len(FACET_CATEGORIES) > 0

    def test_search_modes_contain_required(self):
        assert "keyword" in SEARCH_MODES
        assert "semantic" in SEARCH_MODES
        assert "hybrid" in SEARCH_MODES


class TestChooseRandom:
    """Test the random selection helpers with a seeded RNG."""

    def test_choose_random_query_deterministic(self):
        import random

        rng = random.Random(42)  # noqa: S311 — seeded RNG for deterministic test
        q1 = choose_random_query(rng)
        rng2 = random.Random(42)  # noqa: S311
        q2 = choose_random_query(rng2)
        assert q1 == q2

    def test_choose_random_mode_in_pool(self):
        mode = choose_random_mode()
        assert mode in SEARCH_MODES


# ===================================================================
# locustfile.py — build_search_params
# ===================================================================


class TestBuildSearchParams:
    """Test search parameter construction."""

    def test_basic_keyword_search(self):
        params = build_search_params("python", mode="keyword")
        assert params["q"] == "python"
        assert params["mode"] == "keyword"
        assert params["page"] == 1
        assert params["page_size"] == 10

    def test_semantic_search_custom_page(self):
        params = build_search_params("deep learning", mode="semantic", page=3, page_size=25)
        assert params["q"] == "deep learning"
        assert params["mode"] == "semantic"
        assert params["page"] == 3
        assert params["page_size"] == 25

    def test_facet_filters_included(self):
        params = build_search_params(
            "ai",
            fq_author="Smith",
            fq_category="Science",
            fq_language="en",
        )
        assert params["fq_author"] == "Smith"
        assert params["fq_category"] == "Science"
        assert params["fq_language"] == "en"

    def test_none_filters_excluded(self):
        params = build_search_params("test")
        assert "fq_author" not in params
        assert "fq_category" not in params
        assert "fq_language" not in params


# ===================================================================
# locustfile.py — build_facet_params
# ===================================================================


class TestBuildFacetParams:
    """Test facet parameter construction."""

    def test_empty_params(self):
        params = build_facet_params()
        assert params == {}

    def test_with_query(self):
        params = build_facet_params(query="python")
        assert params == {"q": "python"}

    def test_with_filters(self):
        params = build_facet_params(fq_author="Jones", fq_category="Math")
        assert params["fq_author"] == "Jones"
        assert params["fq_category"] == "Math"
        assert "q" not in params


# ===================================================================
# locustfile.py — build_books_params
# ===================================================================


class TestBuildBooksParams:
    """Test books list parameter construction."""

    def test_defaults(self):
        params = build_books_params()
        assert params == {"page": 1, "page_size": 20}

    def test_custom_values(self):
        params = build_books_params(page=3, page_size=50)
        assert params == {"page": 3, "page_size": 50}


# ===================================================================
# locustfile.py — make_tiny_pdf
# ===================================================================


class TestMakeTinyPdf:
    """Validate the minimal PDF generator."""

    def test_returns_bytes(self):
        pdf = make_tiny_pdf()
        assert isinstance(pdf, bytes)

    def test_starts_with_pdf_header(self):
        pdf = make_tiny_pdf()
        assert pdf.startswith(b"%PDF-")

    def test_ends_with_eof(self):
        pdf = make_tiny_pdf()
        assert pdf.rstrip().endswith(b"%%EOF")

    def test_reasonable_size(self):
        pdf = make_tiny_pdf()
        assert 100 < len(pdf) < 10_000


# ===================================================================
# locustfile.py — parse_search_response
# ===================================================================


class TestParseSearchResponse:
    """Test search response parsing."""

    def test_full_response(self):
        data = {
            "total": 42,
            "results": [{"id": "1"}, {"id": "2"}],
            "facets": {"author": [("Smith", 10)]},
        }
        parsed = parse_search_response(data)
        assert parsed["total"] == 42
        assert parsed["result_count"] == 2
        assert parsed["has_facets"] is True

    def test_empty_response(self):
        parsed = parse_search_response({})
        assert parsed["total"] == 0
        assert parsed["result_count"] == 0
        assert parsed["has_facets"] is False

    def test_no_facets(self):
        data = {"total": 5, "results": [{"id": "1"}]}
        parsed = parse_search_response(data)
        assert parsed["has_facets"] is False


# ===================================================================
# locustfile.py — scenario definitions
# ===================================================================


class TestScenarioDefinitions:
    """Validate the SCENARIOS dict from locustfile."""

    def test_all_three_scenarios_exist(self):
        assert "light" in SCENARIOS
        assert "medium" in SCENARIOS
        assert "heavy" in SCENARIOS

    def test_light_scenario_values(self):
        s = SCENARIOS["light"]
        assert s["users"] == 5
        assert s["spawn_rate"] == 1
        assert s["weights"]["search"] == 80
        assert s["weights"]["browse"] == 20

    def test_medium_scenario_values(self):
        s = SCENARIOS["medium"]
        assert s["users"] == 10
        assert s["weights"]["upload"] == 20

    def test_heavy_scenario_values(self):
        s = SCENARIOS["heavy"]
        assert s["users"] == 25
        assert s["weights"]["admin"] == 25


class TestGetScenario:
    """Test scenario selection from environment."""

    def test_default_returns_medium(self, monkeypatch):
        monkeypatch.delenv("LOCUST_SCENARIO", raising=False)
        scenario = get_scenario()
        assert scenario["users"] == 10

    def test_env_override(self, monkeypatch):
        monkeypatch.setenv("LOCUST_SCENARIO", "heavy")
        scenario = get_scenario()
        assert scenario["users"] == 25

    def test_invalid_falls_back_to_default(self, monkeypatch):
        monkeypatch.setenv("LOCUST_SCENARIO", "nonexistent")
        scenario = get_scenario()
        assert scenario["users"] == 10  # medium fallback


# ===================================================================
# test_concurrent.py — LoadScenario dataclass
# ===================================================================


class TestLoadScenario:
    """Test the LoadScenario dataclass."""

    def test_creation(self):
        s = LoadScenario(name="test", users=5, spawn_rate=1, run_time_seconds=30)
        assert s.name == "test"
        assert s.users == 5

    def test_frozen(self):
        s = LoadScenario(name="test", users=5, spawn_rate=1, run_time_seconds=30)
        with pytest.raises(AttributeError):
            s.users = 10  # type: ignore[misc]

    def test_concurrent_scenarios_defined(self):
        names = [s.name for s in CONCURRENT_SCENARIOS]
        assert "light" in names
        assert "medium" in names
        assert "heavy" in names


# ===================================================================
# test_concurrent.py — build_locust_command
# ===================================================================


class TestBuildLocustCommand:
    """Test CLI command construction."""

    def test_basic_command(self):
        scenario = LoadScenario("test", users=5, spawn_rate=1, run_time_seconds=60)
        cmd = build_locust_command(scenario, host="http://localhost:8080")
        assert cmd[0] == "locust"
        assert "--headless" in cmd
        assert "-u" in cmd
        idx = cmd.index("-u")
        assert cmd[idx + 1] == "5"

    def test_csv_prefix(self, tmp_path):
        scenario = LoadScenario("test", users=5, spawn_rate=1, run_time_seconds=60)
        csv_prefix = str(tmp_path / "results")  # use pytest tmp_path instead of hardcoded /tmp
        cmd = build_locust_command(scenario, host="http://localhost:8080", csv_prefix=csv_prefix)
        assert "--csv" in cmd
        idx = cmd.index("--csv")
        assert cmd[idx + 1] == csv_prefix

    def test_host_included(self):
        scenario = LoadScenario("test", users=5, spawn_rate=1, run_time_seconds=60)
        cmd = build_locust_command(scenario, host="http://example.com")
        idx = cmd.index("--host")
        assert cmd[idx + 1] == "http://example.com"

    def test_run_time_format(self):
        scenario = LoadScenario("test", users=5, spawn_rate=1, run_time_seconds=120)
        cmd = build_locust_command(scenario, host="http://localhost:8080")
        idx = cmd.index("--run-time")
        assert cmd[idx + 1] == "120s"

    def test_locustfile_path_exists(self):
        scenario = LoadScenario("test", users=5, spawn_rate=1, run_time_seconds=60)
        cmd = build_locust_command(scenario, host="http://localhost:8080")
        idx = cmd.index("-f")
        locustfile_path = cmd[idx + 1]
        assert Path(locustfile_path).exists()


# ===================================================================
# test_concurrent.py — parse_locust_csv_stats
# ===================================================================


class TestParseLocustCsvStats:
    """Test CSV parsing logic."""

    def test_missing_file_returns_empty(self, tmp_path):
        result = parse_locust_csv_stats(tmp_path / "nonexistent.csv")
        assert result == []

    def test_valid_csv(self, tmp_path):
        csv_file = tmp_path / "stats.csv"
        csv_file.write_text(
            "Type,Name,Request Count,Failure Count,Average Response Time,"
            "Requests/s,50%,95%,99%\n"
            "GET,/search,100,1,150.5,5.2,120,300,500\n"
            ",,Aggregated,200,2,140.0,10.5,110,280,480\n"
        )
        rows = parse_locust_csv_stats(csv_file)
        assert len(rows) == 2


# ===================================================================
# test_concurrent.py — summarise_locust_run
# ===================================================================


class TestSummariseLocustRun:
    """Test summary generation from CSV rows."""

    def test_aggregated_row(self):
        rows = [
            {
                "Name": "Aggregated",
                "Request Count": "500",
                "Failure Count": "3",
                "Requests/s": "12.5",
                "Average Response Time": "145.2",
                "50%": "120",
                "95%": "300",
                "99%": "500",
            }
        ]
        summary = summarise_locust_run(rows)
        assert summary["total_requests"] == 500
        assert summary["total_failures"] == 3
        assert summary["requests_per_second"] == 12.5
        assert summary["p95_ms"] == 300.0
        assert summary["error_rate_percent"] == 0.6

    def test_no_aggregated_row(self):
        rows = [{"Name": "/search", "Request Count": "100"}]
        summary = summarise_locust_run(rows)
        assert "error" in summary

    def test_empty_rows(self):
        summary = summarise_locust_run([])
        assert "error" in summary


# ===================================================================
# test_concurrent.py — check_pass_criteria
# ===================================================================


class TestCheckPassCriteria:
    """Test pass/fail evaluation against PRD targets."""

    def test_all_pass(self):
        summary = {
            "requests_per_second": 15.0,
            "error_rate_percent": 0.5,
            "p95_ms": 500,
        }
        criteria = check_pass_criteria(summary, users=10)
        assert criteria["throughput_10rps_at_10u"] is True
        assert criteria["error_rate_below_1pct"] is True
        assert criteria["p95_below_2000ms"] is True

    def test_low_throughput_fails_at_10_users(self):
        summary = {
            "requests_per_second": 5.0,
            "error_rate_percent": 0.1,
            "p95_ms": 500,
        }
        criteria = check_pass_criteria(summary, users=10)
        assert criteria["throughput_10rps_at_10u"] is False

    def test_throughput_check_skipped_below_10_users(self):
        summary = {
            "requests_per_second": 3.0,
            "error_rate_percent": 0.1,
            "p95_ms": 500,
        }
        criteria = check_pass_criteria(summary, users=5)
        assert criteria["throughput_10rps_at_10u"] is True  # not applicable

    def test_high_error_rate_fails(self):
        summary = {
            "requests_per_second": 20.0,
            "error_rate_percent": 2.5,
            "p95_ms": 500,
        }
        criteria = check_pass_criteria(summary, users=10)
        assert criteria["error_rate_below_1pct"] is False

    def test_high_p95_fails(self):
        summary = {
            "requests_per_second": 20.0,
            "error_rate_percent": 0.1,
            "p95_ms": 3000,
        }
        criteria = check_pass_criteria(summary, users=10)
        assert criteria["p95_below_2000ms"] is False

    def test_missing_keys_fail_safely(self):
        criteria = check_pass_criteria({}, users=25)
        assert criteria["throughput_10rps_at_10u"] is False
        assert criteria["error_rate_below_1pct"] is False
        assert criteria["p95_below_2000ms"] is False
