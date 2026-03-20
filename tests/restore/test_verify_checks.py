"""
Unit tests for post-restore verification logic.

These tests exercise the pure verification functions in ``verify_checks.py``
using synthetic data.  They run locally without Docker, Solr, Redis, etc.
"""

from __future__ import annotations

import pytest

from verify_checks import (
    CheckResult,
    CheckStatus,
    VerificationReport,
    verify_admin_ui_accessible,
    verify_auth_db_integrity,
    verify_auth_login,
    verify_collections_db_integrity,
    verify_compose_services,
    verify_disk_usage,
    verify_no_log_errors,
    verify_rabbitmq_accessible,
    verify_rabbitmq_exchanges,
    verify_rabbitmq_queues,
    verify_redis_key_count,
    verify_redis_ping,
    verify_solr_cluster_status,
    verify_solr_doc_count,
    verify_solr_query,
)

# =========================================================================
# CheckResult & VerificationReport tests
# =========================================================================


class TestCheckResult:
    """Unit tests for the CheckResult dataclass."""

    def test_pass_result(self):
        r = CheckResult(name="test", status=CheckStatus.PASS, message="ok")
        assert r.passed is True
        assert r.as_dict()["status"] == "PASS"

    def test_fail_result(self):
        r = CheckResult(name="test", status=CheckStatus.FAIL, message="bad")
        assert r.passed is False

    def test_skip_result(self):
        r = CheckResult(name="test", status=CheckStatus.SKIP, message="skipped")
        assert r.passed is False
        assert r.status == CheckStatus.SKIP

    def test_as_dict_includes_details(self):
        r = CheckResult(
            name="check1",
            status=CheckStatus.PASS,
            message="ok",
            details={"count": 42},
        )
        d = r.as_dict()
        assert d["details"]["count"] == 42
        assert d["name"] == "check1"


class TestVerificationReport:
    """Unit tests for the VerificationReport aggregate."""

    def test_empty_report_passes(self):
        report = VerificationReport()
        assert report.all_passed is True
        assert report.pass_count == 0
        assert report.fail_count == 0

    def test_all_pass(self):
        report = VerificationReport()
        report.add(CheckResult(name="a", status=CheckStatus.PASS, message="ok"))
        report.add(CheckResult(name="b", status=CheckStatus.PASS, message="ok"))
        assert report.all_passed is True
        assert report.pass_count == 2
        assert report.fail_count == 0

    def test_one_fail_means_not_all_passed(self):
        report = VerificationReport()
        report.add(CheckResult(name="a", status=CheckStatus.PASS, message="ok"))
        report.add(CheckResult(name="b", status=CheckStatus.FAIL, message="bad"))
        assert report.all_passed is False
        assert report.fail_count == 1

    def test_skip_does_not_cause_failure(self):
        report = VerificationReport()
        report.add(CheckResult(name="a", status=CheckStatus.PASS, message="ok"))
        report.add(CheckResult(name="b", status=CheckStatus.SKIP, message="skipped"))
        assert report.all_passed is True
        assert report.skip_count == 1

    def test_summary_line_pass(self):
        report = VerificationReport()
        report.add(CheckResult(name="a", status=CheckStatus.PASS, message="ok"))
        assert "[PASS]" in report.summary_line()
        assert "1/1 passed" in report.summary_line()

    def test_summary_line_fail(self):
        report = VerificationReport()
        report.add(CheckResult(name="a", status=CheckStatus.FAIL, message="bad"))
        assert "[FAIL]" in report.summary_line()

    def test_format_human_contains_all_checks(self):
        report = VerificationReport()
        report.add(CheckResult(name="check_alpha", status=CheckStatus.PASS, message="ok"))
        report.add(CheckResult(name="check_beta", status=CheckStatus.FAIL, message="bad"))
        output = report.format_human()
        assert "check_alpha" in output
        assert "check_beta" in output
        assert "Post-Restore Verification Report" in output

    def test_format_ci_tab_separated(self):
        report = VerificationReport()
        report.add(CheckResult(name="c1", status=CheckStatus.PASS, message="ok"))
        output = report.format_ci()
        lines = output.strip().split("\n")
        assert lines[0] == "PASS\tc1\tok"

    def test_mixed_report_counts(self):
        report = VerificationReport()
        report.add(CheckResult(name="a", status=CheckStatus.PASS, message="ok"))
        report.add(CheckResult(name="b", status=CheckStatus.FAIL, message="bad"))
        report.add(CheckResult(name="c", status=CheckStatus.SKIP, message="skip"))
        report.add(CheckResult(name="d", status=CheckStatus.PASS, message="ok"))
        assert report.pass_count == 2
        assert report.fail_count == 1
        assert report.skip_count == 1
        assert report.all_passed is False


# =========================================================================
# Solr verification tests
# =========================================================================


class TestVerifySolrClusterStatus:
    """Unit tests for verify_solr_cluster_status."""

    def _healthy_cluster(self, *, num_nodes: int = 3, num_shards: int = 1) -> dict:
        """Build a realistic healthy CLUSTERSTATUS response."""
        nodes = [f"solr{i}:8983_solr" for i in range(1, num_nodes + 1)]
        replicas = {}
        for i, node in enumerate(nodes):
            replicas[f"core_node{i + 1}"] = {
                "state": "active",
                "node_name": node,
                "core": f"books_shard1_replica_n{i + 1}",
            }
        shards = {}
        for s in range(1, num_shards + 1):
            shards[f"shard{s}"] = {"state": "active", "replicas": replicas}
        return {
            "cluster": {
                "live_nodes": nodes,
                "collections": {
                    "books": {
                        "shards": shards,
                        "router": {"name": "compositeId"},
                    }
                },
            }
        }

    def test_healthy_3_node_cluster(self):
        data = self._healthy_cluster(num_nodes=3)
        result = verify_solr_cluster_status(data)
        assert result.passed
        assert result.details["live_nodes"] == 3

    def test_single_node_cluster(self):
        data = self._healthy_cluster(num_nodes=1)
        result = verify_solr_cluster_status(data)
        assert result.passed

    def test_no_live_nodes(self):
        data = {"cluster": {"live_nodes": [], "collections": {"books": {}}}}
        result = verify_solr_cluster_status(data)
        assert not result.passed
        assert "No live Solr nodes" in result.message

    def test_missing_books_collection(self):
        data = {
            "cluster": {
                "live_nodes": ["node1:8983_solr"],
                "collections": {"other": {}},
            }
        }
        result = verify_solr_cluster_status(data)
        assert not result.passed
        assert "'books' collection not found" in result.message

    def test_shard_with_no_active_replicas(self):
        data = {
            "cluster": {
                "live_nodes": ["node1:8983_solr"],
                "collections": {
                    "books": {
                        "shards": {
                            "shard1": {
                                "replicas": {
                                    "core1": {
                                        "state": "down",
                                        "node_name": "node1:8983_solr",
                                    }
                                }
                            }
                        }
                    }
                },
            }
        }
        result = verify_solr_cluster_status(data)
        assert not result.passed
        assert "shard1" in result.message

    def test_multiple_shards_partial_failure(self):
        data = {
            "cluster": {
                "live_nodes": ["node1:8983_solr"],
                "collections": {
                    "books": {
                        "shards": {
                            "shard1": {
                                "replicas": {
                                    "core1": {"state": "active", "node_name": "node1:8983_solr"}
                                }
                            },
                            "shard2": {
                                "replicas": {
                                    "core2": {"state": "recovering", "node_name": "node1:8983_solr"}
                                }
                            },
                        }
                    }
                },
            }
        }
        result = verify_solr_cluster_status(data)
        assert not result.passed
        assert "shard2" in result.message
        assert "shard1" not in result.message

    def test_empty_response(self):
        result = verify_solr_cluster_status({})
        assert not result.passed


class TestVerifySolrDocCount:
    """Unit tests for verify_solr_doc_count."""

    def test_sufficient_docs(self):
        data = {"response": {"numFound": 1000, "docs": []}}
        result = verify_solr_doc_count(data, min_docs=100)
        assert result.passed
        assert result.details["numFound"] == 1000

    def test_zero_docs_with_zero_min(self):
        data = {"response": {"numFound": 0, "docs": []}}
        result = verify_solr_doc_count(data, min_docs=0)
        assert result.passed

    def test_insufficient_docs(self):
        data = {"response": {"numFound": 5, "docs": []}}
        result = verify_solr_doc_count(data, min_docs=100)
        assert not result.passed
        assert "5 docs" in result.message

    def test_empty_response(self):
        result = verify_solr_doc_count({}, min_docs=1)
        assert not result.passed

    def test_exact_minimum(self):
        data = {"response": {"numFound": 100, "docs": []}}
        result = verify_solr_doc_count(data, min_docs=100)
        assert result.passed


class TestVerifySolrQuery:
    """Unit tests for verify_solr_query."""

    def test_query_with_results(self):
        data = {"response": {"numFound": 42, "docs": []}}
        result = verify_solr_query(data, query="python programming")
        assert result.passed
        assert "42 result(s)" in result.message

    def test_query_with_no_results(self):
        data = {"response": {"numFound": 0, "docs": []}}
        result = verify_solr_query(data, query="nonexistent_xyz")
        assert not result.passed
        assert "0 results" in result.message

    def test_query_label_sanitization(self):
        data = {"response": {"numFound": 1, "docs": []}}
        result = verify_solr_query(data, query="hello world!")
        assert "hello_world" in result.name


# =========================================================================
# Redis verification tests
# =========================================================================


class TestVerifyRedisPing:
    """Unit tests for verify_redis_ping."""

    def test_pong_response(self):
        assert verify_redis_ping("PONG").passed

    def test_lowercase_pong(self):
        assert verify_redis_ping("pong").passed

    def test_pong_with_whitespace(self):
        assert verify_redis_ping("  PONG  ").passed

    def test_none_response(self):
        result = verify_redis_ping(None)
        assert not result.passed

    def test_wrong_response(self):
        result = verify_redis_ping("ERROR")
        assert not result.passed

    def test_empty_string(self):
        result = verify_redis_ping("")
        assert not result.passed


class TestVerifyRedisKeyCount:
    """Unit tests for verify_redis_key_count."""

    def test_sufficient_keys(self):
        result = verify_redis_key_count(500, min_keys=100)
        assert result.passed

    def test_zero_keys_zero_min(self):
        result = verify_redis_key_count(0, min_keys=0)
        assert result.passed

    def test_insufficient_keys(self):
        result = verify_redis_key_count(5, min_keys=100)
        assert not result.passed

    def test_none_dbsize(self):
        result = verify_redis_key_count(None, min_keys=0)
        assert not result.passed


# =========================================================================
# RabbitMQ verification tests
# =========================================================================


class TestVerifyRabbitMQAccessible:
    """Unit tests for verify_rabbitmq_accessible."""

    def test_status_200(self):
        assert verify_rabbitmq_accessible(200).passed

    def test_status_401(self):
        result = verify_rabbitmq_accessible(401)
        assert not result.passed

    def test_status_none(self):
        result = verify_rabbitmq_accessible(None)
        assert not result.passed

    def test_status_500(self):
        result = verify_rabbitmq_accessible(500)
        assert not result.passed


class TestVerifyRabbitMQQueues:
    """Unit tests for verify_rabbitmq_queues."""

    def test_expected_queues_present(self):
        queues = [{"name": "indexing"}, {"name": "notifications"}]
        result = verify_rabbitmq_queues(queues, expected_queues=["indexing"])
        assert result.passed

    def test_expected_queues_missing(self):
        queues = [{"name": "indexing"}]
        result = verify_rabbitmq_queues(queues, expected_queues=["indexing", "notifications"])
        assert not result.passed
        assert "notifications" in result.message

    def test_no_expected_queues_some_present(self):
        queues = [{"name": "q1"}, {"name": "q2"}]
        result = verify_rabbitmq_queues(queues)
        assert result.passed
        assert "2 queue(s)" in result.message

    def test_no_expected_queues_none_present(self):
        result = verify_rabbitmq_queues([])
        assert not result.passed

    def test_all_expected_queues_present(self):
        queues = [{"name": "a"}, {"name": "b"}, {"name": "c"}]
        result = verify_rabbitmq_queues(queues, expected_queues=["a", "b", "c"])
        assert result.passed
        assert "3 expected" in result.message


class TestVerifyRabbitMQExchanges:
    """Unit tests for verify_rabbitmq_exchanges."""

    def test_expected_exchanges_present(self):
        exchanges = [{"name": ""}, {"name": "amq.direct"}, {"name": "custom"}]
        result = verify_rabbitmq_exchanges(exchanges, expected_exchanges=["amq.direct"])
        assert result.passed

    def test_expected_exchanges_missing(self):
        exchanges = [{"name": "amq.direct"}]
        result = verify_rabbitmq_exchanges(exchanges, expected_exchanges=["custom"])
        assert not result.passed

    def test_no_expected_exchanges(self):
        exchanges = [{"name": ""}, {"name": "amq.direct"}]
        result = verify_rabbitmq_exchanges(exchanges)
        assert result.passed


# =========================================================================
# Auth / collections DB verification tests
# =========================================================================


class TestVerifyAuthDBIntegrity:
    """Unit tests for verify_auth_db_integrity."""

    def test_healthy_auth_db(self):
        result = verify_auth_db_integrity(table_names=["users", "sessions"], user_count=5)
        assert result.passed
        assert "5 user(s)" in result.message

    def test_missing_users_table(self):
        result = verify_auth_db_integrity(table_names=["sessions"], user_count=5)
        assert not result.passed
        assert "'users' table not found" in result.message

    def test_zero_users(self):
        result = verify_auth_db_integrity(table_names=["users"], user_count=0)
        assert not result.passed

    def test_none_user_count(self):
        result = verify_auth_db_integrity(table_names=["users"], user_count=None)
        assert not result.passed

    def test_single_user(self):
        result = verify_auth_db_integrity(table_names=["users"], user_count=1)
        assert result.passed


class TestVerifyCollectionsDBIntegrity:
    """Unit tests for verify_collections_db_integrity."""

    def test_no_tables_skips(self):
        result = verify_collections_db_integrity(table_names=[])
        assert result.status == CheckStatus.SKIP

    def test_tables_present(self):
        result = verify_collections_db_integrity(table_names=["collections", "items"])
        assert result.passed
        assert "2 table(s)" in result.message


# =========================================================================
# Docker Compose service verification tests
# =========================================================================


class TestVerifyComposeServices:
    """Unit tests for verify_compose_services."""

    def test_all_running(self):
        statuses = {"solr1": "running", "redis": "running", "rabbitmq": "running"}
        result = verify_compose_services(statuses)
        assert result.passed

    def test_one_exited(self):
        statuses = {"solr1": "running", "redis": "exited", "rabbitmq": "running"}
        result = verify_compose_services(statuses)
        assert not result.passed
        assert "redis" in result.message

    def test_empty_services(self):
        result = verify_compose_services({})
        assert not result.passed

    def test_expected_services_all_present(self):
        statuses = {"solr1": "running", "redis": "running"}
        result = verify_compose_services(statuses, expected_services=["solr1", "redis"])
        assert result.passed

    def test_expected_services_missing(self):
        statuses = {"solr1": "running"}
        result = verify_compose_services(statuses, expected_services=["solr1", "redis"])
        assert not result.passed
        assert "redis" in result.message

    def test_restarting_service(self):
        statuses = {"app": "restarting"}
        result = verify_compose_services(statuses)
        assert not result.passed


# =========================================================================
# Log error detection tests
# =========================================================================


class TestVerifyNoLogErrors:
    """Unit tests for verify_no_log_errors."""

    def test_clean_logs(self):
        lines = [
            "2024-01-01 INFO Starting service",
            "2024-01-01 INFO Health check passed",
            "2024-01-01 DEBUG Processing request",
        ]
        result = verify_no_log_errors(lines)
        assert result.passed

    def test_error_detected(self):
        lines = [
            "2024-01-01 INFO Starting service",
            "2024-01-01 ERROR Connection refused",
            "2024-01-01 INFO Retrying...",
        ]
        result = verify_no_log_errors(lines)
        assert not result.passed
        assert "1 error(s)" in result.message

    def test_fatal_detected(self):
        lines = ["2024-01-01 FATAL Out of memory"]
        result = verify_no_log_errors(lines)
        assert not result.passed

    def test_traceback_detected(self):
        lines = [
            "Traceback (most recent call last):",
            "  File 'app.py', line 10, in <module>",
            "ValueError: invalid input",
        ]
        result = verify_no_log_errors(lines)
        assert not result.passed

    def test_false_positive_excluded_error_log_path(self):
        lines = [
            "nginx: error_log /var/log/nginx/error.log notice;",
        ]
        result = verify_no_log_errors(lines)
        assert result.passed

    def test_false_positive_excluded_loglevel(self):
        lines = [
            "Setting loglevel to error for production",
        ]
        result = verify_no_log_errors(lines)
        assert result.passed

    def test_empty_logs(self):
        result = verify_no_log_errors([])
        assert result.passed

    def test_max_errors_threshold(self):
        lines = [
            "2024-01-01 ERROR Timeout 1",
            "2024-01-01 ERROR Timeout 2",
        ]
        result = verify_no_log_errors(lines, max_errors=2)
        assert result.passed

    def test_multiple_error_types(self):
        lines = [
            "2024-01-01 ERROR Connection refused",
            "2024-01-01 FATAL Shutting down",
            "PANIC: kernel error",
        ]
        result = verify_no_log_errors(lines)
        assert not result.passed
        assert result.details["error_count"] == 3

    def test_error_reporting_excluded(self):
        lines = ["ERROR_REPORTING=E_ALL & ~E_DEPRECATED"]
        result = verify_no_log_errors(lines)
        assert result.passed

    def test_exception_in_thread_detected(self):
        lines = ["Exception in thread 'main' java.lang.NullPointerException"]
        result = verify_no_log_errors(lines)
        assert not result.passed


# =========================================================================
# Disk usage tests
# =========================================================================


class TestVerifyDiskUsage:
    """Unit tests for verify_disk_usage."""

    def test_normal_usage(self):
        result = verify_disk_usage(45.0)
        assert result.passed
        assert "45.0%" in result.message

    def test_high_usage(self):
        result = verify_disk_usage(95.0)
        assert not result.passed

    def test_custom_threshold(self):
        result = verify_disk_usage(85.0, max_percent=80.0)
        assert not result.passed

    def test_exactly_at_threshold(self):
        result = verify_disk_usage(90.0, max_percent=90.0)
        assert result.passed

    def test_none_usage(self):
        result = verify_disk_usage(None)
        assert result.status == CheckStatus.SKIP

    def test_zero_usage(self):
        result = verify_disk_usage(0.0)
        assert result.passed


# =========================================================================
# Admin UI tests
# =========================================================================


class TestVerifyAdminUIAccessible:
    """Unit tests for verify_admin_ui_accessible."""

    def test_status_200(self):
        assert verify_admin_ui_accessible(200).passed

    def test_status_302_redirect(self):
        assert verify_admin_ui_accessible(302).passed

    def test_status_404(self):
        result = verify_admin_ui_accessible(404)
        assert not result.passed

    def test_status_500(self):
        result = verify_admin_ui_accessible(500)
        assert not result.passed

    def test_status_none(self):
        result = verify_admin_ui_accessible(None)
        assert not result.passed


# =========================================================================
# Auth login tests
# =========================================================================


class TestVerifyAuthLogin:
    """Unit tests for verify_auth_login."""

    def test_successful_login(self):
        result = verify_auth_login(status_code=200, has_token=True)
        assert result.passed

    def test_login_no_token(self):
        result = verify_auth_login(status_code=200, has_token=False)
        assert not result.passed

    def test_login_401(self):
        result = verify_auth_login(status_code=401, has_token=False)
        assert not result.passed

    def test_no_credentials_skips(self):
        result = verify_auth_login(status_code=None)
        assert result.status == CheckStatus.SKIP


# =========================================================================
# End-to-end report assembly test
# =========================================================================


class TestFullVerificationReport:
    """Test building a complete verification report from multiple checks."""

    def test_all_passing_report(self):
        report = VerificationReport()

        # Solr
        cluster = {
            "cluster": {
                "live_nodes": ["n1:8983_solr", "n2:8983_solr", "n3:8983_solr"],
                "collections": {
                    "books": {
                        "shards": {
                            "shard1": {
                                "replicas": {
                                    "r1": {"state": "active", "node_name": "n1:8983_solr"}
                                }
                            }
                        }
                    }
                },
            }
        }
        report.add(verify_solr_cluster_status(cluster))
        report.add(verify_solr_doc_count({"response": {"numFound": 500}}, min_docs=100))
        report.add(verify_solr_query({"response": {"numFound": 10}}, query="test"))

        # Redis
        report.add(verify_redis_ping("PONG"))
        report.add(verify_redis_key_count(200, min_keys=0))

        # RabbitMQ
        report.add(verify_rabbitmq_accessible(200))
        report.add(verify_rabbitmq_queues([{"name": "indexing"}]))

        # Auth
        report.add(verify_auth_db_integrity(["users"], 3))
        report.add(verify_collections_db_integrity(["collections"]))

        # Services
        report.add(verify_compose_services({"solr1": "running", "redis": "running"}))
        report.add(verify_no_log_errors(["INFO all good"]))
        report.add(verify_disk_usage(50.0))
        report.add(verify_admin_ui_accessible(200))
        report.add(verify_auth_login(200, has_token=True))

        assert report.all_passed
        assert report.pass_count == 14
        assert report.fail_count == 0

        human = report.format_human()
        assert "Post-Restore Verification Report" in human
        assert "[PASS]" in report.summary_line()

    def test_mixed_report(self):
        report = VerificationReport()
        report.add(verify_solr_cluster_status({}))  # FAIL
        report.add(verify_redis_ping("PONG"))  # PASS
        report.add(verify_auth_login(None))  # SKIP
        report.add(verify_disk_usage(95.0))  # FAIL

        assert not report.all_passed
        assert report.pass_count == 1
        assert report.fail_count == 2
        assert report.skip_count == 1

        ci_output = report.format_ci()
        assert "FAIL" in ci_output
        assert "PASS" in ci_output
        assert "SKIP" in ci_output
