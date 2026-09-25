import io
import json
import ssl
import unittest
import urllib.error
from dataclasses import FrozenInstanceError
from datetime import date, datetime, timedelta
from pathlib import Path
from threading import Barrier, Thread
from unittest.mock import Mock, patch
from urllib.parse import parse_qs, urlsplit

from fake_transport import CERTS, NOW, VIN, client_pair, login_data, page, session
from leapmotor_cloud.cloud import ALLOWED_HOSTS, CENTER_ORIGIN, GLOBAL_ORIGIN, ApiError, ProtocolError
from leapmotor_cloud.errors import ValidationError
from leapmotor_cloud.history import calendar_window
from leapmotor_cloud.session import AuthenticationRequired, CloudSession, SessionExpired, SessionStore
from leapmotor_cloud.signing import sign_authenticated
from leapmotor_cloud.transport import Request, Response, TransportError, UrllibTransport, _NoRedirect


class NoNetwork(unittest.TestCase):
    def setUp(self):
        self.socket_patch = patch("socket.socket", side_effect=AssertionError("Real network forbidden"))
        self.socket_patch.start()
        self.addCleanup(self.socket_patch.stop)


class SessionTests(NoNetwork):
    def test_key_and_private_immutable_material(self):
        value = session()
        self.assertEqual(value.key, bytes(range(96, 128)))
        self.assertNotIn(value.token, repr(value))
        self.assertNotIn(value.user_id, repr(value))
        with self.assertRaises(FrozenInstanceError):
            value.token = "changed"

    def test_expiry_metadata_and_override(self):
        expiry = NOW + timedelta(seconds=60)
        self.assertEqual(session({"exp": expiry.timestamp()}).expires_at, expiry)
        self.assertEqual(session({"exp": 0}, expires_at=expiry).expires_at, expiry)
        self.assertFalse(session().expiry_known)
        session().ensure_valid(NOW + timedelta(days=365))

    def test_invalid_expiry(self):
        for value in (True, "123", None, [], float("inf")):
            with self.subTest(value=value), self.assertRaises(ValidationError):
                session({"exp": value})
        with self.assertRaises(ValidationError):
            session(expires_at=datetime(2026, 1, 1))

    def test_invalid_material(self):
        for change in ({"accountId": True}, {"accountId": -1}, {"signParam": None}, {"token": "bad"}):
            data = login_data()
            data.update(change)
            with self.subTest(change=change), self.assertRaises(ValidationError):
                CloudSession.from_login_data(data, device_id="device", client_cert=CERTS)
        with self.assertRaises(ValidationError):
            CloudSession.from_login_data(login_data(), device_id="", client_cert=CERTS)

    def test_empty_and_expired_store(self):
        with self.assertRaises(AuthenticationRequired):
            SessionStore().get(NOW)
        client, fake, _ = client_pair(session(expires_at=NOW))
        with self.assertRaises(SessionExpired):
            client.resolve_vehicle_route(VIN)
        self.assertEqual(fake.requests, [])

    def test_store_validation(self):
        store = SessionStore()
        with self.assertRaises(ValidationError):
            store.replace({})
        with self.assertRaises(ValidationError):
            store.get(datetime(2026, 1, 1))

    def test_atomic_replacement(self):
        first, second = session(), session(expires_at=NOW + timedelta(hours=1))
        store = SessionStore()
        store.replace(first)
        barrier, errors = Barrier(4), []
        def run(index):
            try:
                barrier.wait(timeout=3)
                for _ in range(100):
                    store.replace(first if index % 2 else second)
                    if store.get(NOW) is not first and store.get(NOW) is not second:
                        # Compare one atomic snapshot, not two separately observed states.
                        snapshot = store.get(NOW)
                        if snapshot is not first and snapshot is not second:
                            errors.append("mixed session")
            except Exception as error:
                errors.append(type(error).__name__)
        workers = [Thread(target=run, args=(i,)) for i in range(4)]
        for worker in workers:
            worker.start()
        for worker in workers:
            worker.join(timeout=5)
        self.assertFalse(any(worker.is_alive() for worker in workers))
        self.assertEqual(errors, [])


class CloudTests(NoNetwork):
    def setUp(self):
        super().setUp()
        self.client, self.fake, self.store = client_pair()

    def test_route_signature_and_certificate(self):
        self.fake.route()
        route = self.client.resolve_vehicle_route(VIN)
        request = self.fake.requests[0]
        self.assertEqual(request.method, "GET")
        self.assertIsNone(request.body)
        self.assertEqual(parse_qs(urlsplit(request.url).query), {"vin": [VIN]})
        keys = ("source", "channel", "acceptLanguage", "version", "deviceType", "nonce", "timestamp", "deviceId")
        core = {k: request.headers[k] for k in keys}
        self.assertEqual(request.headers["sign"], sign_authenticated(session().key, core, {"vin": VIN}))
        self.assertEqual(self.fake.certificates, [CERTS])
        self.assertNotIn(VIN, repr(route))

    def test_statistics_dates_and_immutable_response(self):
        self.fake.route()
        self.fake.queue_json({"result": "0", "data": {"extra": [{"energy": None}]}})
        result = self.client.get_charge_statistics(VIN, date(2026, 9, 18), date(2026, 9, 24))
        body = json.loads(self.fake.requests[-1].body)
        self.assertEqual(body["startTime"], "2026-09-18")
        self.assertEqual(body["endTime"], "2026-09-24")
        with self.assertRaises(TypeError):
            result["extra"][0]["energy"] = 2

    def test_availability_routes(self):
        for kind in ("charge", "mileage"):
            self.fake.route()
            self.fake.queue_json({"code": 0, "data": {"startTime": 1}})
            self.assertEqual(self.client.get_history_availability(VIN, kind=kind)["startTime"], 1)
            self.assertTrue(self.fake.requests[-1].url.endswith(f"/{kind}/vail/startTime/query"))

    def test_bad_input_before_transport(self):
        for vin in (None, "", "a/b", "a\n"):
            with self.assertRaises(ValidationError):
                self.client.resolve_vehicle_route(vin)
        with self.assertRaises(ValidationError):
            self.client.get_history_availability(VIN, kind="unknown")
        with self.assertRaises(ValidationError):
            self.client.get_charge_statistics(VIN, date(2026, 9, 25), date(2026, 9, 24))
        self.assertEqual(self.fake.requests, [])

    def test_route_mismatch_and_untrusted_origins(self):
        for overrides in ({"vin": "OTHER"}, {"appCenter": "https://evil.invalid"},
                          {"appCenter": CENTER_ORIGIN + "/path"}, {"appCenter": CENTER_ORIGIN + ":444"},
                          {"appCenter": CENTER_ORIGIN.replace("https:", "http:")},
                          {"appRegion": "https://evil.invalid"}):
            client, fake, _ = client_pair()
            fake.route(**overrides)
            with self.subTest(overrides=overrides), self.assertRaises(ProtocolError):
                client.resolve_vehicle_route(VIN)
            self.assertEqual(len(fake.requests), 1)

    def test_nonzero_codes_are_errors(self):
        for codes in ({"code": 0, "result": 5}, {"code": "302010205"}, {"code": -1, "result": 0}):
            self.fake.queue_json(dict(codes, data={}, message="private-message"))
            with self.assertRaises(ApiError) as caught:
                self.client.resolve_vehicle_route(VIN)
            self.assertNotIn("private-message", str(caught.exception))

    def test_malformed_envelopes(self):
        for data in ([], {}, {"code": True}, {"code": None}, {"code": 0}, {"code": 0, "data": []}):
            self.fake.queue_json(data)
            with self.subTest(data=data), self.assertRaises(ProtocolError):
                self.client.resolve_vehicle_route(VIN)

    def test_invalid_json_and_duplicate_keys(self):
        for raw in (b"not-json", b"\xff", b'{"code":0,"code":1,"data":{}}', b'{"code":0,"data":{"n":NaN}}'):
            self.fake.responses.append(Response(200, raw))
            with self.assertRaises(ProtocolError):
                self.client.resolve_vehicle_route(VIN)

    def test_http_errors_no_retry(self):
        for status in (401, 403, 302, 500):
            client, fake, _ = client_pair()
            fake.responses.append(Response(status, b"private"))
            with self.assertRaises(AuthenticationRequired if status in (401, 403) else TransportError):
                client.resolve_vehicle_route(VIN)
            self.assertEqual(len(fake.requests), 1)

    def test_session_snapshot_across_routing(self):
        old = self.store.get(NOW)
        replacement = session({"exp": (NOW + timedelta(hours=1)).timestamp()})
        self.fake.on_send = lambda: self.store.replace(replacement)
        self.fake.route()
        self.fake.queue_json({"code": 0, "data": {}})
        self.client.get_history_availability(VIN, kind="charge")
        self.assertEqual([r.headers["token"] for r in self.fake.requests], [old.token, old.token])

    def test_expiry_between_route_and_data(self):
        times = iter((NOW, NOW, NOW + timedelta(seconds=10)))
        client, fake, _ = client_pair(session(expires_at=NOW + timedelta(seconds=5)), clock=lambda: next(times))
        fake.route()
        with self.assertRaises(SessionExpired):
            client.get_history_availability(VIN, kind="charge")
        self.assertEqual(len(fake.requests), 1)

    def test_no_generic_or_control_surface(self):
        for name in ("request", "execute", "login", "refresh"):
            self.assertFalse(hasattr(self.client, name))
        with self.assertRaises(ValidationError):
            self.client._send(session(), GLOBAL_ORIGIN, "/remote/control", {})
        self.assertEqual(self.fake.requests, [])


class HistoryTests(NoNetwork):
    def read(self, pages, *, charges=False, **kwargs):
        client, fake, _ = client_pair()
        fake.route()
        for value in pages:
            fake.queue_json(value)
        method = client.list_charges if charges else client.list_trips
        result = method(VIN, date(2026, 9, 23), date(2026, 9, 23), timezone="Europe/Rome", **kwargs)
        return result, fake

    def test_dst_calendar_windows(self):
        for day, hours in ((date(2026, 3, 29), 23), (date(2026, 10, 25), 25), (date(2026, 9, 20), 24)):
            start, end = calendar_window(day, day, "Europe/Rome")
            self.assertEqual(end - start + 1, hours * 3600)
        self.assertEqual(calendar_window(date(2026, 9, 20), date(2026, 9, 20), "Europe/Rome"), (1789855200, 1789941599))
        start, end = calendar_window(date(2026, 3, 28), date(2026, 3, 30), "Europe/Rome")
        self.assertEqual(end - start + 1, 71 * 3600)

    def test_invalid_dates_and_bounds(self):
        for start, end, zone in ((date.max, date.max, "UTC"), (NOW, NOW, "UTC"),
                                 (date(2026, 9, 24), date(2026, 9, 23), "UTC"),
                                 (date(2026, 9, 23), date(2026, 9, 23), "Missing/Zone")):
            with self.assertRaises(ValidationError):
                calendar_window(start, end, zone)
        for limit in (True, 0, -1, 101, 1.5):
            client, fake, _ = client_pair()
            with self.assertRaises(ValidationError):
                client.list_trips(VIN, date(2026, 9, 23), date(2026, 9, 23), timezone="UTC", max_pages=limit)
            self.assertEqual(fake.requests, [])

    def test_two_pages_preserve_raw_units_and_unknown_fields(self):
        rows = [{"id": n, "energy": None, "time": 1789855200000, "extra": [1, 2]} for n in range(21)]
        result, fake = self.read([page(rows[:20], total=21), page(rows[20:], number=2, total=21)])
        self.assertTrue(result.complete)
        self.assertEqual(len(result.records), 21)
        self.assertEqual(result.records[0]["time"], 1789855200000)
        self.assertIsNone(result.records[0]["energy"])
        self.assertEqual(result.records[0]["extra"], (1, 2))
        with self.assertRaises(TypeError):
            result.records[0]["id"] = 999
        self.assertNotIn("1789855200000", repr(result))
        self.assertEqual(len(fake.requests), 3)

    def test_page_parameter_types_and_valid_empty(self):
        for charges in (False, True):
            result, fake = self.read([page([])], charges=charges)
            body = json.loads(fake.requests[-1].body)
            self.assertIs(type(body["pageNum"]), str if charges else int)
            self.assertIs(type(body["pageSize"]), str if charges else int)
            self.assertIs(type(body["startTime"]), str)
            self.assertTrue(result.complete)
            self.assertEqual(result.reason, "empty")

    def test_repeated_page_preserved_and_incomplete(self):
        rows = [{"id": n} for n in range(20)]
        result, _ = self.read([page(rows, total=40), page(rows, number=2, total=40)])
        self.assertFalse(result.complete)
        self.assertEqual(result.reason, "repeated_page")
        self.assertEqual(len(result.records), 40)

    def test_duplicate_records_not_removed(self):
        result, _ = self.read([page([{"id": 1}, {"id": 1}])])
        self.assertEqual(result.reason, "duplicate_records")
        self.assertEqual(len(result.records), 2)

    def test_page_limit(self):
        result, fake = self.read([page([{"id": n} for n in range(20)], total=21)], max_pages=1)
        self.assertFalse(result.complete)
        self.assertEqual(result.reason, "page_limit")
        self.assertEqual(len(fake.requests), 2)

    def test_totals_changed(self):
        result, _ = self.read([page([{"id": n} for n in range(20)], total=21),
                               page([{"id": 20}, {"id": 21}], number=2, total=22)])
        self.assertEqual(result.reason, "totals_changed")
        self.assertEqual(len(result.records), 22)

    def test_bad_metadata_and_records_raise(self):
        for change in ({"total": -1}, {"total": True}, {"pageNum": "1"}, {"pageSize": 10},
                       {"list": None}, {"list": [1]}, {"list": [{}] * 21}):
            data = page([])
            data["data"].update(change)
            with self.subTest(change=change), self.assertRaises(ProtocolError):
                self.read([data])
        data = page([])
        del data["data"]["list"]
        with self.assertRaises(ProtocolError):
            self.read([data])

    def test_inconsistent_results_not_complete(self):
        for value, reason in ((page([{"id": 1}], total=2), "record_count_mismatch"),
                              (page([], total=1), "empty_page_before_total"),
                              (page([{"id": 1}], total=1, pages=2), "inconsistent_totals")):
            result, _ = self.read([value])
            self.assertFalse(result.complete)
            self.assertEqual(result.reason, reason)


class Stream(io.BytesIO):
    def __init__(self, body=b"{}", status=200):
        super().__init__(body)
        self.status, self.read_sizes = status, []

    def getcode(self):
        return self.status

    def read(self, size=-1):
        self.read_sizes.append(size)
        return super().read(size)


class TransportTests(NoNetwork):
    def setUp(self):
        super().setUp()
        self.context = Mock(verify_flags=0)
        self.ssl_patch = patch("leapmotor_cloud.transport.ssl.create_default_context", return_value=self.context)
        self.opener_patch = patch("leapmotor_cloud.transport.urllib.request.build_opener")
        self.ssl_factory = self.ssl_patch.start()
        self.opener_factory = self.opener_patch.start()
        self.addCleanup(self.ssl_patch.stop)
        self.addCleanup(self.opener_patch.stop)
        self.opener = self.opener_factory.return_value
        self.transport = UrllibTransport(Path("synthetic-ca.pem"), ALLOWED_HOSTS)
        self.request = Request("POST", CENTER_ORIGIN + "/read", {"token": "synthetic"}, b"{}")

    def test_tls_and_explicit_certificate(self):
        self.opener.open.return_value = Stream()
        self.assertEqual(self.transport.send(self.request, client_cert=CERTS).status, 200)
        self.assertTrue(self.context.check_hostname)
        self.assertEqual(self.context.verify_mode, ssl.CERT_REQUIRED)
        self.assertTrue(self.context.verify_flags & ssl.VERIFY_X509_PARTIAL_CHAIN)
        self.context.load_cert_chain.assert_called_once_with(str(CERTS[0]), str(CERTS[1]))
        self.ssl_factory.assert_called_once_with(cafile="synthetic-ca.pem")
        self.assertEqual(self.opener_factory.call_args.args[0].proxies, {})
        self.assertEqual(self.opener.open.call_args.kwargs["timeout"], 15)

    def test_reject_url_before_tls(self):
        for url in ("http://appgateway.leapmotor-international.de", "https://evil.invalid", CENTER_ORIGIN + ":444",
                    CENTER_ORIGIN + "#fragment", "https://user@appgateway.leapmotor-international.de", CENTER_ORIGIN + "\n"):
            with self.assertRaises(ValidationError):
                self.transport.send(Request("GET", url, {}), client_cert=CERTS)
        self.ssl_factory.assert_not_called()
        self.opener_factory.assert_not_called()

    def test_redirects_refused(self):
        for status in (301, 302, 307, 308):
            self.opener.open.return_value = Stream(status=status)
            with self.assertRaises(TransportError) as caught:
                self.transport.send(self.request, client_cert=CERTS)
            self.assertEqual(caught.exception.reason, "redirect_refused")
        with self.assertRaises(TransportError):
            _NoRedirect().redirect_request(None, None, 302, "", {}, "https://evil.invalid")
        self.assertEqual(self.opener.open.call_count, 4)

    def test_bounded_body_and_stream_closed(self):
        stream = Stream(b"x" * (1048576 + 1))
        self.opener.open.return_value = stream
        with self.assertRaises(TransportError) as caught:
            self.transport.send(self.request, client_cert=CERTS)
        self.assertEqual(caught.exception.reason, "response_too_large")
        self.assertEqual(stream.read_sizes, [1048577])
        self.assertTrue(stream.closed)

    def test_network_errors_redacted(self):
        for error in (OSError("private-token"), urllib.error.URLError("private-token"), ssl.SSLError("private-token")):
            self.opener.open.side_effect = error
            with self.assertRaises(TransportError) as caught:
                self.transport.send(self.request, client_cert=CERTS)
            self.assertNotIn("private-token", str(caught.exception))

    def test_http_error_preserves_status(self):
        self.opener.open.side_effect = urllib.error.HTTPError(CENTER_ORIGIN, 401, "Denied", {}, io.BytesIO(b"{}"))
        self.assertEqual(self.transport.send(self.request, client_cert=CERTS).status, 401)

    def test_forbidden_headers(self):
        for header in ("Host", "Cookie", "Proxy-Authorization"):
            with self.assertRaises(ValidationError):
                self.transport.send(Request("GET", CENTER_ORIGIN, {header: "x"}), client_cert=CERTS)
        self.opener_factory.assert_not_called()

    def test_invalid_configuration(self):
        for timeout in (True, 0, -1, float("inf")):
            with self.assertRaises(ValidationError):
                UrllibTransport(Path("ca.pem"), ALLOWED_HOSTS, timeout=timeout)
        for limit in (True, 0, 16777217):
            with self.assertRaises(ValidationError):
                UrllibTransport(Path("ca.pem"), ALLOWED_HOSTS, max_response_bytes=limit)
        with self.assertRaises(ValidationError):
            self.transport.send(self.request, client_cert=None)

    def test_request_immutable_and_redacted(self):
        headers = {"token": "secret-value"}
        value = Request("POST", CENTER_ORIGIN + "/private", headers, b"private-body")
        headers["token"] = "changed"
        self.assertEqual(value.headers["token"], "secret-value")
        self.assertNotIn("secret-value", repr(value))
        self.assertNotIn("private", repr(value))
        for headers in ({"x": "a\nb"}, {"X": "a", "x": "b"}, {"bad key": "a"}):
            with self.assertRaises(ValidationError):
                Request("GET", CENTER_ORIGIN, headers)
        with self.assertRaises(ValidationError):
            Request("GET", CENTER_ORIGIN, {}, b"body")


if __name__ == "__main__":
    unittest.main()
