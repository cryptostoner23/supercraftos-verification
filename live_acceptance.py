"""Run the live acceptance task once, and record what it did.

    python3 live_acceptance.py [--key IDEMPOTENCY_KEY]

The task is submitted with an idempotency key so a repeated run cannot
submit the same request twice by accident. The key defaults to a fresh one
per run, so each run is a real acceptance run, and it can be given
explicitly to re-run the same one.
"""
import asyncio, json, os, sys, time, uuid
from pathlib import Path
from job_store import JobStore
from agent_runtime import AgentWorker

QUERY = ('Build a standalone Python CSV expense summarizer. Accept date,category,amount columns and '
         'output category totals to JSON using exact decimal currency arithmetic. Reject missing required '
         'columns, malformed amounts, NaN, infinity and negative values with clear errors. Include a CLI, '
         'a README with usage, and meaningful unittest cases including a Unicode category and empty input. '
         'Run the tests and a real CLI example, inspect the output, then deliver the files. Use only the '
         'Python standard library. Explain actions briefly and save one reusable lesson after verification.')


def idempotency_key() -> str:
    for index, value in enumerate(sys.argv):
        if value == '--key' and index + 1 < len(sys.argv):
            return sys.argv[index + 1]
    return f"live-release-acceptance-{uuid.uuid4().hex[:12]}"


async def main():
    store = JobStore()
    job = store.submit(QUERY, max_steps=24, idempotency_key=idempotency_key())
    Path('data/live-acceptance-job.json').write_text(json.dumps({'id': job['id'], 'started': time.time()}))
    worker = AgentWorker(store=store)
    await worker.run_once()
    final = store.get(job['id'])
    result = {k: final[k] for k in ('id', 'status', 'steps', 'error', 'result')}
    Path('data/live-acceptance-result.json').write_text(json.dumps(result, indent=2))
    print(json.dumps({'id': final['id'], 'status': final['status'], 'steps': final['steps'], 'error': final['error']}), flush=True)
    if final['status'] != 'completed': raise SystemExit(1)


if __name__ == '__main__':
    asyncio.run(main())
