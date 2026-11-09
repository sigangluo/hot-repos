import asyncio

import httpx
import pytest

from hot_repos.github.client import MAX_ATTEMPTS, GitHubClient, GitHubError, rate_limit_wait


async def no_sleep(_):
    pass


def client_for(handler):
    return GitHubClient("t", rps=1e6, transport=httpx.MockTransport(handler), sleep=no_sleep)


def get(handler, url="https://api.github.com/x", **kwargs):
    async def go():
        async with client_for(handler) as c:
            return await c.get(url, **kwargs), c.requests

    return asyncio.run(go())


def test_returns_404_to_caller():
    response, _ = get(lambda r: httpx.Response(404))
    assert response.status_code == 404


def test_retries_server_errors():
    codes = iter([502, 503, 200])
    response, requests = get(lambda r: httpx.Response(next(codes)))
    assert response.status_code == 200
    assert requests == 3


def test_retries_network_errors():
    calls = []

    def handler(request):
        calls.append(1)
        if len(calls) == 1:
            raise httpx.ConnectError("boom")
        return httpx.Response(200)

    response, _ = get(handler)
    assert response.status_code == 200


def test_retries_requested_status():
    codes = iter([202, 200])
    response, _ = get(lambda r: httpx.Response(next(codes)), retry_statuses=(202,))
    assert response.status_code == 200


def test_secondary_rate_limit_is_retried():
    codes = iter([403, 200])

    def handler(request):
        code = next(codes)
        return httpx.Response(code, json={"message": "You have exceeded a secondary rate limit."})

    response, requests = get(handler)
    assert response.status_code == 200
    assert requests == 2


def test_plain_403_is_not_retried():
    response, requests = get(lambda r: httpx.Response(403, json={"message": "Forbidden"}))
    assert response.status_code == 403
    assert requests == 1


def test_gives_up_after_max_attempts():
    with pytest.raises(GitHubError, match="重跑即可续上"):
        get(lambda r: httpx.Response(500))


def test_gives_up_after_max_attempts_counts_requests():
    count = []

    def handler(request):
        count.append(1)
        return httpx.Response(500)

    with pytest.raises(GitHubError):
        get(handler)
    assert len(count) == MAX_ATTEMPTS


def test_rate_limit_wait_uses_reset_header_for_primary_limit():
    response = httpx.Response(
        403, headers={"x-ratelimit-remaining": "0", "x-ratelimit-reset": "1100"}, text="x"
    )
    assert rate_limit_wait(response, now=1000) == 102


def test_rate_limit_wait_honors_retry_after():
    response = httpx.Response(429, headers={"retry-after": "120"}, text="x")
    assert rate_limit_wait(response) == 120


def test_rate_limit_wait_ignores_other_responses():
    assert rate_limit_wait(httpx.Response(200)) is None
    assert rate_limit_wait(httpx.Response(403, text="contributors list too large")) is None


def test_rate_limit_waits_do_not_use_up_attempts():
    codes = iter([403] * (MAX_ATTEMPTS + 3) + [200])

    def handler(request):
        code = next(codes)
        return httpx.Response(code, json={"message": "You have exceeded a secondary rate limit."})

    response, _ = get(handler)
    assert response.status_code == 200


def test_max_attempts_can_be_lowered():
    count = []

    def handler(request):
        count.append(1)
        return httpx.Response(502)

    with pytest.raises(GitHubError):

        async def go():
            async with client_for(handler) as c:
                await c.get("https://api.github.com/x", max_attempts=3)

        asyncio.run(go())
    assert len(count) == 3


def test_invalid_json_body_is_retried_when_json_is_expected():
    bodies = iter([b"", b"<html>oops</html>", b'{"ok": true}'])
    response, requests = get(lambda r: httpx.Response(200, content=next(bodies)), expect_json=True)
    assert response.json() == {"ok": True}
    assert requests == 3


def test_invalid_json_body_is_returned_when_json_is_not_expected():
    response, requests = get(lambda r: httpx.Response(200, content=b"plain"))
    assert response.text == "plain"
    assert requests == 1
