"""Automatic local capability execution and outcome-driven routing policy."""
import asyncio
import json
import re
import sqlite3
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DB = ROOT / 'data/capability-outcomes.sqlite3'


def capabilities():
    DB.parent.mkdir(exist_ok=True)
    with sqlite3.connect(DB, timeout=10) as database:
        database.execute('CREATE TABLE IF NOT EXISTS outcomes (capability TEXT, success INTEGER, elapsed REAL, at REAL)')
        rows = database.execute('SELECT capability, COUNT(*), SUM(success), AVG(elapsed) FROM outcomes GROUP BY capability').fetchall()
    usage = {row[0]: row for row in rows}
    definitions = [('cad', 'Physical product execution', 'Idea → validated parameters → actual STEP/STL/DXF; geometry and process checks', (ROOT / '.cad-venv/bin/python').exists()),
                   ('json', 'Structured data transformation', 'Parse, validate and format JSON locally without inference', True),
                   ('workflow', 'Durable agent workflow', 'Planner/builder, restartable checkpoints, failure memory, tools and approvals', True)]
    result = []
    for identifier, name, features, ready in definitions:
        row = usage.get(identifier, (identifier, 0, 0, 0))
        successes = row[2] or 0
        result.append({'id': identifier, 'name': name, 'features': features, 'enabled': ready,
                       'runs': row[1], 'successes': successes, 'mean_seconds': round(row[3] or 0, 3),
                       'routing_score': round((successes + 1) / (row[1] + 2), 3)})
    result.sort(key=lambda item: (item['enabled'], item['routing_score']), reverse=True)
    return {'capabilities': result, 'policy': 'Automatically applied from installed capability checks and measured success/latency. Public reviews inform design priorities; they do not execute unreviewed third-party code.', 'checked_at': time.time()}


def record(identifier, success, elapsed):
    capabilities()
    with sqlite3.connect(DB, timeout=10) as database:
        database.execute('INSERT INTO outcomes VALUES (?,?,?,?)', (identifier, int(success), elapsed, time.time()))
        database.execute('DELETE FROM outcomes WHERE rowid NOT IN (SELECT rowid FROM outcomes ORDER BY at DESC LIMIT 1000)')
    refresh_policy()


def refresh_policy():
    result = capabilities()
    target = ROOT / 'data/applied-capability-policy.json'
    import tempfile, os
    fd, temporary = tempfile.mkstemp(dir=target.parent)
    with os.fdopen(fd, 'w') as stream: json.dump(result, stream, indent=2)
    os.replace(temporary, target)
    return result


async def execute_request(query):
    """Return a real local artifact for supported intents; None selects agents."""
    if re.search(r'\b(cad|enclosure|mounting plate|bracket|stl|step file)\b', query, re.I):
        identifier = 'cad'
    elif re.search(r'\b(format|validate|pretty.print)\b.*\bjson\b', query, re.I):
        identifier = 'json'
    else: return None
    begin = time.monotonic()
    try:
        policy = {item['id']: item for item in refresh_policy()['capabilities']}
        selected = policy[identifier]
        if not selected['enabled']: raise RuntimeError('Requested native capability is unavailable')
        if selected['runs'] >= 3 and selected['routing_score'] < .25:
            return None
        if identifier == 'cad':
            from product_design import interpret_idea, build_product
            spec = await interpret_idea(query)
            result = await asyncio.to_thread(build_product, spec)
        else:
            candidate = query[query.find('{'):] if '{' in query else query[query.find('['):]
            if not candidate:
                raise ValueError('A JSON object or array is required')
            value, end = json.JSONDecoder().raw_decode(candidate)
            # raw_decode intentionally accepts a valid prefix.  Treat trailing
            # non-whitespace as a malformed request so the native capability
            # never silently drops user data while claiming validation.
            if candidate[end:].strip():
                raise ValueError('Trailing content after JSON value')
            result = {'formatted_json': json.dumps(value, indent=2, ensure_ascii=False), 'validated': True}
        await asyncio.to_thread(record, identifier, True, time.monotonic()-begin)
        return {'capability': identifier, 'result': result}
    except Exception:
        await asyncio.to_thread(record, identifier, False, time.monotonic()-begin)
        raise
