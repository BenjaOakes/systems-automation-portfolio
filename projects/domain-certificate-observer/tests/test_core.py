import unittest
from datetime import datetime, timezone, timedelta

from domain_observer.cli import main
from domain_observer.core import CertificateRecord, DomainObserver, ObserverConfig, check_expiry_status, exit_code, notify_results, valid_domain


class DomainObserverTests(unittest.TestCase):
    def test_expiry_states_are_deterministic(self):
        now = datetime(2030, 1, 1, tzinfo=timezone.utc)
        self.assertEqual(check_expiry_status(now - timedelta(days=1), now=now), "expired")
        self.assertEqual(check_expiry_status(now + timedelta(days=3), now=now), "critical")
        self.assertEqual(check_expiry_status(now + timedelta(days=20), now=now), "warning")
        self.assertEqual(check_expiry_status(now + timedelta(days=90), now=now), "healthy")

    def test_observer_uses_injected_probes_and_reports_errors(self):
        def resolver(domain, timeout):
            return ["192.0.2.20"]

        def tls(domain, timeout):
            return CertificateRecord(datetime(2099, 1, 1, tzinfo=timezone.utc), "Synthetic CA", domain)

        observer = DomainObserver(ObserverConfig(cache_ttl_seconds=60), resolver=resolver, certificate_probe=tls)
        result = observer.observe(["Docs.Brand-A.Example", "docs.brand-a.example"])[0]
        self.assertEqual(result.domain, "docs.brand-a.example")
        self.assertEqual(result.dns_addresses, ("192.0.2.20",))
        self.assertEqual(result.expiry_status, "healthy")
        self.assertEqual(exit_code([result]), 0)

    def test_invalid_domain_is_not_queried(self):
        observer = DomainObserver(resolver=lambda *_: self.fail("resolver called"), certificate_probe=lambda *_: self.fail("tls called"))
        result = observer.observe_domain("bad domain")
        self.assertIn("invalid_domain", result.errors)

    def test_domain_validation_rejects_private_or_malformed_input(self):
        self.assertTrue(valid_domain("api.example.com"))
        self.assertFalse(valid_domain("localhost"))
        self.assertFalse(valid_domain("bad domain.example"))

    def test_empty_dns_result_is_cached(self):
        calls = 0

        def resolver(domain, timeout):
            nonlocal calls
            calls += 1
            return []

        observer = DomainObserver(
            ObserverConfig(cache_ttl_seconds=60),
            resolver=resolver,
            certificate_probe=lambda *_: CertificateRecord(datetime(2099, 1, 1, tzinfo=timezone.utc)),
        )
        observer.observe_domain("empty.example")
        observer.observe_domain("empty.example")
        self.assertEqual(calls, 1)

    def test_notification_is_only_called_when_a_sink_is_supplied(self):
        received = []
        notify_results([], lambda results: received.extend(results))
        self.assertEqual(received, [])

    def test_zero_cache_ttl_disables_reuse(self):
        calls = 0

        def resolver(domain, timeout):
            nonlocal calls
            calls += 1
            return ["192.0.2.20"]

        observer = DomainObserver(
            ObserverConfig(cache_ttl_seconds=0),
            resolver=resolver,
            certificate_probe=lambda *_: CertificateRecord(datetime(2099, 1, 1, tzinfo=timezone.utc)),
        )
        observer.observe_domain("brand-a.example")
        observer.observe_domain("brand-a.example")
        self.assertEqual(calls, 2)

    def test_missing_input_uses_documented_invalid_input_exit_code(self):
        with self.assertRaises(SystemExit) as raised:
            main([])
        self.assertEqual(raised.exception.code, 2)


if __name__ == "__main__":
    unittest.main()
