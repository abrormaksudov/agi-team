import asyncio

import httpx
import pytest
from agi_agent.app import bearer, page_hint, state, user_of
from fastapi import HTTPException


def test_page_hint_names_the_table_and_its_fqn():
    hint = page_hint("/table/greenplum.dwh.datamart.x/schema")

    assert "table" in hint
    assert "`greenplum.dwh.datamart.x`" in hint


@pytest.mark.parametrize("page", ["/table/%22a.b%22", '/table/"a.b"'])
def test_page_hint_unquotes_and_strips_quotes_from_fqn(page):
    hint = page_hint(page)

    assert "`a.b`" in hint
    assert '"' not in hint


@pytest.mark.parametrize("page", ["/explore/tables", None])
def test_page_hint_is_empty_for_unknown_route_or_no_page(page):
    assert page_hint(page) == ""


def who(responses: list[httpx.Response], token: str = "tok") -> tuple[str | HTTPException, list[httpx.Request]]:
    """Run user_of against a fake OM that answers /users/loggedInUser with the given responses in turn."""
    seen = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return responses[len(seen) - 1]

    async def run():
        state["http"] = httpx.AsyncClient(transport=httpx.MockTransport(handler))
        state["users"] = {}
        try:
            return [await user_of(token), await user_of(token)]
        except HTTPException as e:
            return e
        finally:
            await state["http"].aclose()

    return asyncio.run(run()), seen


def test_user_of_asks_om_who_the_token_belongs_to_and_caches_it():
    names, seen = who([httpx.Response(200, json={"name": "jury"})])

    assert names == ["jury", "jury"]
    assert len(seen) == 1
    assert seen[0].url.path == "/api/v1/users/loggedInUser"
    assert seen[0].headers["Authorization"] == "Bearer tok"


def test_user_of_turns_a_rejected_token_into_401():
    err, _ = who([httpx.Response(401, json={})])

    assert isinstance(err, HTTPException)
    assert err.status_code == 401


@pytest.mark.parametrize("header", [None, "", "Basic abc", "bearer abc"])
def test_bearer_requires_a_bearer_header(header):
    with pytest.raises(HTTPException) as err:
        bearer(header)

    assert err.value.status_code == 401


def test_bearer_returns_the_token():
    assert bearer("Bearer abc ") == "abc"
