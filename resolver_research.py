"""Current source research for liquidity arbitrage and a 1inch Fusion resolver."""
from __future__ import annotations
import asyncio
import json
from datetime import datetime, timezone
from pathlib import Path
from context_service import ContextService, ContextRequestError
from notion_db_setup import private_json
from runtime_env import ROOT

GOAL = 'Liquidity arbitrage, MEV infrastructure, and a 1inch Fusion resolver'
QUERY = '1inch Fusion resolver SDK settlement Dutch auction liquidity arbitrage requirements (site:github.com/1inch OR site:business.1inch.com OR site:docs.1inch.io)'
DOMAINS = ['github.com', 'business.1inch.com', 'docs.1inch.io']


class ResolverResearch:
    def __init__(self, context=None):
        self.context = context

    async def collect(self, num_results=3):
        owned = self.context is None
        service = self.context or ContextService()
        try:
            response = await service.search(QUERY, num_results=num_results, include_domains=DOMAINS, fresh=True)
        finally:
            if owned:
                await service.close()
        sources = []
        for item in response.get('results', []):
            markdown = item.get('markdown') or {}
            sources.append({'title': item.get('title', ''), 'url': item.get('url', ''), 'description': item.get('description', ''), 'markdown_status': markdown.get('code', 'NOT_REQUESTED'), 'markdown': markdown.get('markdown') if markdown.get('code') == 'SUCCESS' else None})
        result = {'goal': GOAL, 'request_id': response.get('request_id'), 'checked_at': datetime.now(timezone.utc).isoformat(), 'partial': response.get('partial', False), 'fresh_page_content_requested': True, 'sources': sources, 'research_status': 'sources_returned' if sources else 'empty', 'execution_status': 'research_only', 'cache_metadata': response.get('cache_metadata')}
        private_json(ROOT / 'data' / 'context-resolver-research.json', result)
        private_json(ROOT / 'data' / 'context-live-response.json', response)
        return result


def summary(result):
    return {k: ([{a:b for a,b in source.items() if a not in {'markdown','description'}} for source in value] if k == 'sources' else value) for k,value in result.items()}


async def main():
    try:
        result = await ResolverResearch().collect()
        print(json.dumps(summary(result), indent=2))
        return 0 if result['sources'] else 1
    except ContextRequestError as exc:
        report = {'status':'failed', 'http_status':exc.status, 'error_code':exc.code, 'request_id':exc.request_id}
        private_json(ROOT / 'data' / 'context-live-error.json', report)
        print(json.dumps(report, indent=2))
        return 1


if __name__ == '__main__':
    raise SystemExit(asyncio.run(main()))
