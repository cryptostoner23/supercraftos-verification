"""The sole server-side gateway to Context.dev's official async Python SDK."""
from __future__ import annotations
import asyncio
import os
import random
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from context.dev import AsyncContextDev, APIStatusError, APIConnectionError, APITimeoutError
from runtime_env import load_environment


class ContextRequestError(RuntimeError):
    def __init__(self, status, code, request_id=None):
        self.status, self.code, self.request_id = status, code, request_id
        super().__init__(f'Context.dev request failed: HTTP {status}, {code}, request_id={request_id}')


class ContextService:
    def __init__(self, client=None, *, attempts=3):
        load_environment()
        if client is None and not os.getenv('CONTEXT_DEV_API_KEY'):
            raise RuntimeError('CONTEXT_DEV_API_KEY is not configured')
        self.client = client or AsyncContextDev(base_url='https://api.context.dev/v1', max_retries=0, timeout=70)
        self.owned = client is None
        self.attempts = max(1, min(attempts, 3))

    @staticmethod
    def retry_delay(value, fallback):
        if value:
            try:
                return max(0, float(value))
            except ValueError:
                try:
                    return max(0, (parsedate_to_datetime(value) - datetime.now(timezone.utc)).total_seconds())
                except (TypeError, ValueError):
                    pass
        return fallback

    async def search(self, query, *, num_results=3, include_domains=None, fresh=True):
        """One logical search; per-result Markdown success remains explicit."""
        if not isinstance(query, str) or not 1 <= len(query.strip()) <= 500:
            raise ValueError('query must contain 1–500 characters')
        if type(num_results) is not int or not 1 <= num_results <= 10:
            raise ValueError('num_results must be between 1 and 10')
        arguments = {'query': query, 'num_results': num_results, 'markdown_options': {'enabled': True, 'max_age_ms': 0 if fresh else 86400000, 'use_main_content_only': True}}
        if include_domains:
            arguments['include_domains'] = include_domains
        for attempt in range(self.attempts):
            try:
                response = await self.client.web.search(**arguments)
                return response.model_dump(mode='json', by_alias=True, exclude_none=False)
            except APIStatusError as exc:
                body = exc.body if isinstance(exc.body, dict) else {}
                code = body.get('error_code', 'HTTP_ERROR')
                request_id = body.get('request_id') or exc.response.headers.get('x-request-id')
                transient = exc.status_code in (408, 429) or exc.status_code >= 500
                if not transient or attempt + 1 == self.attempts:
                    raise ContextRequestError(exc.status_code, code, request_id) from None
                delay = self.retry_delay(exc.response.headers.get('Retry-After'), min(8, 2**attempt))
                # Do not retry earlier than a long server-requested backoff.
                if delay > 60:
                    raise ContextRequestError(exc.status_code, 'RETRY_AFTER_EXCEEDS_REQUEST_BUDGET', request_id) from None
                await asyncio.sleep(delay + random.uniform(0, 0.25))
            except (APIConnectionError, APITimeoutError):
                if attempt + 1 == self.attempts:
                    raise ContextRequestError(0, 'TRANSPORT_ERROR') from None
                await asyncio.sleep(min(8, 2**attempt) + random.uniform(0, 0.25))

    async def close(self):
        if self.owned:
            await self.client.close()

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_):
        await self.close()
