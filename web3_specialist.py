"""Authenticated app bridge to the existing local Web3 AI; no chain cache."""
from __future__ import annotations
import httpx

URL = 'http://127.0.0.1:8710/api/brain/chat'

def tool():
    return {'name': 'consult_web3_specialist',
            'description': 'Consult the existing specialist Web3 AI with read-only live research tools: DEX, contract security, yields, gas, portfolio, market and protocol research. Returns its actual mode and observed source calls. No trades, signatures, messages or blockchain history storage. Use for Web3 technical analysis alongside official protocol documentation.',
            'inputSchema': {'type': 'object', 'properties': {'question': {'type': 'string', 'minLength': 3, 'maxLength': 4000}}, 'required': ['question'], 'additionalProperties': False}}

async def consult(arguments):
    question = arguments.get('question')
    if not isinstance(question, str) or not 3 <= len(question.strip()) <= 4000:
        raise ValueError('Provide a question of 3–4000 characters')
    try:
        async with httpx.AsyncClient(timeout=55, trust_env=False) as client:
            response = await client.post(URL, json={'message': question, 'use_llm': True, 'read_only': True})
            response.raise_for_status()
            result = response.json()
    except (httpx.HTTPError, ValueError):
        return {'status': 'unavailable', 'error': 'The local Web3 specialist could not return a response. No result is inferred.'}
    if not isinstance(result, dict) or not isinstance(result.get('answer'), str):
        return {'status': 'unavailable', 'error': 'The specialist returned an invalid response.'}
    return {'status': 'completed', 'specialist': 'existing-web3-brain', 'mode': result.get('mode'),
            'answer': result['answer'], 'tool_calls': result.get('tool_calls', []),
            'limitations': 'Research only. Source failures remain in tool evidence; this does not establish execution or profitability.'}
