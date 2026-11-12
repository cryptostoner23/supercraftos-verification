# Open Uniswap v4 Route Verification Kit

HSK · SuperCraftOS · Python 3.10+ · no runtime dependencies.

Compare independently recorded reference/observed route quotes, validate hop continuity and minimum output, inspect the hook permission bits and dynamic-fee marker, and publish a deterministic JSON receipt and Markdown report. This implements the read-only route-comparison and hook-review evaluation scope of the recorded proposal. It is not a trading bot or a complete PoolManager simulator.

## Run without installation

From this directory:

```sh
python3 -m unittest discover -s tests -v
python3 -m route_verifier fixtures/passing.json --output report
python3 -m route_verifier fixtures/failing.json --output failure-report
```

The last command deliberately exits 1. Exit 0 means all quote/minimum-out comparisons passed; 1 means a comparison failed; 2 means invalid input. Hook review flags never establish that a contract is safe. Reports distinguish quote matches from behavior-review requirements.

Optional installation: `python3 -m pip install .`, then `v4-route-verify fixtures/passing.json --output report`. The module execution above requires no installer, internet, API key, RPC, wallet or stored chain data.

## Data collection and replay method

1. Record a reference quote from a documented v4-compatible quoter and an observed quote from the implementation under evaluation at the **same chain, block, pool state, input and route**. Store provenance alongside the fixture; do not put wallet credentials in it. This tool reads the small local fixture only and never fetches blockchain history.
2. Normalize each hop to `token_in`, `token_out`, `amount_in`, `reference_out`, `observed_out`, `fee` and optional `hook`. Addresses are 20-byte hex; amounts are raw smallest-unit unsigned integer strings, without floating-point conversions. The reference amount is the reference quote for that hop at the observed input amount, not a separate inconsistent reference route.
3. Set each route's `minimum_out` and optional `tolerance_bps` explicitly. The comparator uses `abs(observed-reference)*10000 <= reference*tolerance_bps`; there is no floating point rounding. Zero reference requires zero observed output.
4. Run the CLI and preserve `receipt.json`, `report.md`, fixture and provenance together. The receipt hashes the canonical input for reproducible replay. Demonstration fixtures are synthetic regression vectors, clearly not live quotes.

## Sources and limits

- [Official PoolManager architecture](https://developers.uniswap.org/docs/protocols/v4/concepts/poolmanager)
- [Official v4 hook concepts](https://developers.uniswap.org/docs/protocols/v4/concepts/hooks)
- [Canonical hook permission constants](https://github.com/Uniswap/v4-core/blob/main/src/libraries/Hooks.sol)
- [Canonical dynamic LP fee flag](https://github.com/Uniswap/v4-core/blob/main/src/libraries/LPFeeLibrary.sol)

The tool compares supplied outputs; it does not independently calculate swaps, cross ticks, execute hook bytecode, assess reentrancy or prove market profitability. Snapshot provenance and reference quality must be established by the collector. No grant award, payment or deployed adoption is claimed. Account identity and optional-provider sign-in are not execution dependencies.
