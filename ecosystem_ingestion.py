"""Opt-in protocol ingestion. Disabled by default; accepts API responses, not scraped DOM."""
from __future__ import annotations
import json, urllib.request, urllib.parse, urllib.error
from typing import Any
from dynamic_mcp_server import DynamicMCPServer

# The providers that have a documented, reachable API, read from the
# configuration file. A provider without a credential is not offered, because
# a tool that always fails is worse than no tool.
DESCRIPTIONS = {
    "firecrawl": "Read a public page as Markdown through Firecrawl.",
    "tavily": "Search the live web using Tavily; returns up to three source results. Uses provider credits.",
    "browserless": "Open a public HTTPS page in a cloud browser and return its rendered HTML. Uses browser quota.",
}


def _providers() -> dict[str, dict[str, str]]:
    from token_optimizer import load_config
    section = (load_config().get("ingestion") or {})
    providers = {name: spec for name, spec in section.items()
                 if name in DESCRIPTIONS and isinstance(spec, dict) and spec.get("url") and spec.get("env")}
    providers['firecrawl'] = {'url': 'https://api.firecrawl.dev/v2/scrape', 'env': 'FIRECRAWL_API_KEY'}
    providers['tavily'] = {'url': 'https://api.tavily.com/search', 'env': 'TAVILY_API_KEY'}
    providers['browserless'] = {'url': 'https://production-sfo.browserless.io/content', 'env': 'BROWSERLESS_TOKEN'}
    return providers


class ProtocolIngestion:
    def __init__(self, client=None): self.client=client or self.http
    def http(self,url,headers=None,payload=None):
        req=urllib.request.Request(url,data=None if payload is None else json.dumps(payload).encode(),headers=headers or {},method="POST" if payload else "GET")
        class NoRedirect(urllib.request.HTTPRedirectHandler):
            def redirect_request(self, *args, **kwargs): return None
        try:
            with urllib.request.build_opener(NoRedirect()).open(req,timeout=45) as r:
                raw = r.read(1_500_001)
                if len(raw) > 1_500_000: raise RuntimeError('Provider response exceeded the size limit')
                if 'text/html' in r.headers.get('Content-Type', ''):
                    return {'html': raw.decode('utf-8', 'replace')}
                return json.loads(raw)
        except urllib.error.HTTPError as exc:
            raise RuntimeError(f'Provider request rejected (HTTP {exc.code})') from None
        except (urllib.error.URLError, TimeoutError, OSError, ValueError):
            raise RuntimeError('Provider transport or response failed') from None
    def devhunt_github(self,url,token): return self.client(url,{"Authorization":f"Bearer {token}","Content-Type":"application/json"},{"query":"query { repository(owner:\"devhunt\", name:\"devhunt\") { pullRequests(states:OPEN) { nodes { url title } } } }"})
    def firecrawl(self,url,api_key,target): return self.client(url,{"Authorization":f"Bearer {api_key}","Content-Type":"application/json"},{"url":target,"formats":["markdown"]})
    def peerpush(self,url): return self.client(url)
    def startupage(self,payload): return {"mrr":payload.get("mrr"),"verified":bool(payload.get("stripe_verified"))}
    def synthesize(self, candidates):
        return [{"name":c["name"],"description":c.get("description",""),"inputSchema":{"type":"object","properties":c.get("properties",{})}} for c in candidates if c.get("name")]
    def register(self, candidates, server=None):
        server=server or DynamicMCPServer()
        for tool in self.synthesize(candidates): server.register_new_tool(tool["name"],tool["description"],tool["inputSchema"])
        return server


def available_providers() -> list[dict[str, Any]]:
    """The providers whose credential is present, with their tool schemas."""
    import os
    rows = []
    for name, spec in _providers().items():
        if not os.getenv(spec["env"]):
            continue
        rows.append({
            "name": f"ingest_{name}",
            "description": DESCRIPTIONS.get(name, f"Read data from {name}."),
            "inputSchema": {"type": "object", "properties": {
                "target": {"type": "string", "minLength": 1, "maxLength": 2000}},
                "required": ["target"], "additionalProperties": False},
        })
    return rows


def ingest(arguments: dict[str, Any], *, provider: str | None = None) -> dict[str, Any]:
    """Read one provider's API and return what it said.

    Each bound MCP tool supplies its provider explicitly. Direct callers may
    omit it only when exactly one supported provider is configured.
    """
    import os
    target = arguments.get("target")
    if not isinstance(target, str) or not target.strip():
        raise ValueError("target is required")
    target = target.strip()
    providers = _providers()
    if provider is None:
        configured = [name for name, spec in providers.items() if os.getenv(spec['env'])]
        if len(configured) != 1:
            raise RuntimeError('Select a configured ingestion provider explicitly')
        provider = configured[0]
    if provider not in providers or not os.getenv(providers[provider]['env']):
        raise RuntimeError('Selected ingestion provider credential is not configured')
    spec = providers[provider]; key = os.environ[spec['env']]
    client = ProtocolIngestion()
    if provider in {'firecrawl', 'browserless'}:
        parsed = urllib.parse.urlsplit(target)
        if parsed.scheme != 'https' or not parsed.hostname or parsed.username or parsed.password:
            raise ValueError('A public HTTPS URL without embedded credentials is required')
    if provider == 'firecrawl':
        result = client.firecrawl(spec['url'], key, target)
    elif provider == 'tavily':
        result = client.http(spec['url'], {'Authorization': 'Bearer '+key, 'Content-Type': 'application/json'},
                             {'query': target, 'search_depth': 'basic', 'max_results': 3, 'include_answer': False})
    else:
        result = client.http(spec['url']+'?'+urllib.parse.urlencode({'token':key}),
                             {'Content-Type': 'application/json'}, {'url': target})
    return {'provider': provider, 'result': result}

