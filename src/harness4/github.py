"""Bounded GitHub REST transport. No shell, redirects, or PR code execution."""
from __future__ import annotations

import asyncio
import json
import os
import re
from urllib.parse import quote, unquote

import httpx


class GitHubFailure(ValueError):
    pass


class GitHub:
    def __init__(self, repo: str, *, key_env: str = 'H4_GITHUB_TOKEN', transport=None):
        if not re.fullmatch(r'[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+', repo):
            raise ValueError('Expected owner/repository.')
        self.repo, self.key_env, self.transport = repo, key_env, transport

    async def request(self, method: str, path: str, body=None, *, params=None):
        token = os.environ.get(self.key_env)
        if not token:
            raise GitHubFailure('GitHub credential environment variable is empty.')
        if (not path.startswith('/') or path.startswith('//') or '\\' in path or '?' in path or '#' in path
                or any(part in ('.', '..') for part in unquote(path).split('/'))):
            raise GitHubFailure('Invalid API path.')
        headers = {'Authorization': f'Bearer {token}', 'Accept': 'application/vnd.github+json',
                   'X-GitHub-Api-Version': '2022-11-28'}
        try:
            async with asyncio.timeout(30):
                async with httpx.AsyncClient(base_url='https://api.github.com', headers=headers,
                                             trust_env=False, follow_redirects=False,
                                             transport=self.transport, timeout=30) as client:
                    async with client.stream(method, path, json=body, params=params) as response:
                        if not 200 <= response.status_code < 300:
                            raise GitHubFailure(f'GitHub request failed (HTTP {response.status_code}); no automatic retry.')
                        data = bytearray()
                        async for chunk in response.aiter_bytes():
                            data.extend(chunk)
                            if len(data) > 2_000_000:
                                raise GitHubFailure('GitHub response exceeds the size limit.')
                        return json.loads(data)
        except (httpx.HTTPError, TimeoutError, UnicodeError, json.JSONDecodeError):
            raise GitHubFailure('GitHub transport or response failed; a write may require reconciliation.') from None

    async def api(self, method: str, suffix: str, body=None):
        return await self.request(method, f'/repos/{self.repo}/{suffix}', body)

    async def pages(self, suffix: str, *, field: str | None = None):
        values = []
        for page in range(1, 11):
            result = await self.request('GET', f'/repos/{self.repo}/{suffix}',
                                        params={'per_page': 100, 'page': page})
            batch = result[field] if field else result
            if not isinstance(batch, list):
                raise GitHubFailure('Malformed GitHub page.')
            values.extend(batch)
            if len(batch) < 100:
                if field and result.get('total_count', len(values)) > len(values):
                    raise GitHubFailure('Incomplete GitHub evidence.')
                return values
        raise GitHubFailure('GitHub pagination limit exceeded; human review required.')


def segment(value: str) -> str:
    return quote(value, safe='')
