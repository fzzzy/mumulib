# pyright: standard
import asyncio
import copy
import json
import unittest
from typing import Any
from unittest import mock

from examples import editors
from mumulib.mumutypes import Message


class TestEditors(unittest.TestCase):
    def setUp(self):
        # Each test's own copy of the data, so its writes do not leak
        self.saved = (
            copy.deepcopy(editors.characters),
            copy.deepcopy(editors.parties),
            copy.deepcopy(editors.deploys.records),
        )

    def tearDown(self):
        characters, parties, records = self.saved
        for live, kept in (
            (editors.characters, characters),
            (editors.parties, parties),
            (editors.deploys.records, records),
        ):
            live.clear()
            live.update(kept)

    def request(self, path: str, method: str = "GET", body: object = None):
        """The status and body of one request to the example's app."""
        sent: list[Message] = []
        data = json.dumps(body).encode() if body is not None else b""

        async def send(message: Message) -> None:
            sent.append(message)

        async def receive() -> Message:
            return {"type": "http.request", "body": data, "more_body": False}

        headers = [(b"content-type", b"application/json")] if body is not None else []

        async def go() -> None:
            scope = {"type": "http", "method": method, "path": path, "headers": headers}
            await editors.app({**scope, "state": {}}, receive, send)

        asyncio.run(go())
        content = b"".join(m.get("body", b"") for m in sent[1:]).strip()
        return sent[0]["status"], content

    def json(self, path: str) -> Any:
        status, content = self.request(path)
        self.assertEqual(status, 200, content)
        return json.loads(content)

    def test_each_kind_is_its_records_by_id(self):
        self.assertEqual(set(self.json("/editors/characters.json")), {"c1", "c2", "c3"})
        self.assertEqual(
            self.json("/editors/parties.json")["p1"]["members"], ["c1", "c2"]
        )
        deploys = self.json("/editors/deploys.json")
        self.assertEqual(deploys["d1"]["status"], "running")
        self.assertEqual(self.json("/editors/deploys/d2.json"), deploys["d2"])

    def test_a_character_or_party_is_replaced_whole(self):
        character = {"name": "Renamed", "prompt": "p", "agent_args": ""}
        self.assertEqual(
            self.request("/editors/characters/c1.json", "PUT", character)[0], 204
        )
        self.assertEqual(self.json("/editors/characters/c1.json"), character)
        party = {"name": "Solo", "members": ["c3"]}
        self.assertEqual(self.request("/editors/parties/p1.json", "PUT", party)[0], 204)
        self.assertEqual(self.json("/editors/parties/p1.json"), party)

    def test_a_deploy_takes_a_name_and_a_party_and_its_status_stays(self):
        status, content = self.request(
            "/editors/deploys/d1.json", "PUT", {"name": "Weekly", "party": "p2"}
        )
        self.assertEqual(status, 200)
        self.assertEqual(
            json.loads(content), {"name": "Weekly", "party": "p2", "status": "running"}
        )
        self.assertEqual(self.json("/editors/deploys/d1.json")["party"], "p2")

    def test_a_deploy_refuses_anything_else(self):
        for body in (
            {"name": "x", "party": "p1", "status": "stopped"},
            {"name": "", "party": "p1"},
            {"name": "x", "party": "nowhere"},
            "replaced",
        ):
            with self.subTest(body=body):
                status, _ = self.request("/editors/deploys/d1.json", "PUT", body)
                self.assertEqual(status, 400)
        self.assertEqual(
            self.json("/editors/deploys/d1.json")["name"], "Nightly review"
        )

    def test_an_unknown_deploy_is_not_found(self):
        self.assertEqual(self.request("/editors/deploys/d9.json")[0], 404)
        self.assertEqual(self.request("/editors/deploys/d9.json", "PUT", {})[0], 404)

    def test_each_change_is_announced_by_the_url_of_what_changed(self):
        with mock.patch.object(editors.changes, "put") as put:
            self.request("/editors/characters/c2.json", "PUT", {"name": "x"})
            self.request(
                "/editors/deploys/d2.json", "PUT", {"name": "y", "party": "p1"}
            )
            self.request("/editors/deploys/d2.json", "PUT", {"status": "z"})
        self.assertEqual(
            [call.args[0] for call in put.call_args_list],
            ["/editors/characters/c2", "/editors/deploys/d2"],
        )
