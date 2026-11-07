"""Read-only deterministic Uniswap v4 quote regression and hook-permission analysis."""
import hashlib
import json
import re

PERMISSIONS = ['afterRemoveLiquidityReturnsDelta', 'afterAddLiquidityReturnsDelta',
               'afterSwapReturnsDelta', 'beforeSwapReturnsDelta', 'afterDonate', 'beforeDonate',
               'afterSwap', 'beforeSwap', 'afterRemoveLiquidity', 'beforeRemoveLiquidity',
               'afterAddLiquidity', 'beforeAddLiquidity', 'afterInitialize', 'beforeInitialize']
LIMITATIONS = [
    'Compares supplied reference and observed quotes; it does not independently simulate PoolManager.',
    'Fixtures are reproducible test vectors, not live prices or evidence of profitable execution.',
    'Hook flags identify callable permissions, not an audit of contract behavior.',
    'No RPC, private keys, signatures, transactions or blockchain database are needed.',
]

def integer(value, name, maximum=(1 << 256) - 1):
    if isinstance(value, str) and re.fullmatch(r'0|[1-9][0-9]{0,77}', value):
        value = int(value)
    if type(value) is not int or not 0 <= value <= maximum:
        raise ValueError(f'{name} must be an unsigned integer within range')
    return value


def address(value):
    if not isinstance(value, str) or not re.fullmatch(r'0x[0-9a-fA-F]{40}', value):
        raise ValueError('Invalid EVM address')
    return value.lower()


def permissions(value):
    bits = int(address(value), 16) & ((1 << 14) - 1)
    return [name for bit, name in enumerate(PERMISSIONS) if bits & (1 << bit)]


def evaluate(document):
    if not isinstance(document, dict) or type(document.get('schema_version')) is not int or document.get('schema_version') != 1:
        raise ValueError('Expected schema_version 1')
    routes = document.get('routes')
    if not isinstance(routes, list) or not 1 <= len(routes) <= 64:
        raise ValueError('Provide 1–64 routes')
    names, results = set(), []
    for route in routes:
        if not isinstance(route, dict):
            raise ValueError('Route must be an object')
        name = route.get('id')
        if not isinstance(name, str) or not re.fullmatch(r'[a-zA-Z0-9_-]{1,80}', name) or name in names:
            raise ValueError('Each route requires a unique safe ID')
        names.add(name)
        hops = route.get('hops')
        if not isinstance(hops, list) or not 1 <= len(hops) <= 16:
            raise ValueError('Provide 1–16 hops')
        tolerance = integer(route.get('tolerance_bps', 0), 'tolerance_bps', 10000)
        minimum = integer(route.get('minimum_out', 0), 'minimum_out')
        previous, hop_results, flags = None, [], set()
        for hop in hops:
            if not isinstance(hop, dict):
                raise ValueError('Hop must be an object')
            token_in, token_out = address(hop.get('token_in')), address(hop.get('token_out'))
            if token_in == token_out:
                raise ValueError('A hop must exchange different currencies')
            amount_in = integer(hop.get('amount_in'), 'amount_in')
            reference = integer(hop.get('reference_out'), 'reference_out')
            observed = integer(hop.get('observed_out'), 'observed_out')
            if amount_in == 0:
                raise ValueError('amount_in must be positive')
            if previous and (token_in != previous[0] or amount_in != previous[1]):
                raise ValueError('Observed route must have continuous currencies and amounts')
            fee = integer(hop.get('fee'), 'fee', 0x800000)
            if fee != 0x800000 and fee > 1000000:
                raise ValueError('Fee exceeds 100% and is not the dynamic-fee flag')
            active = permissions(hop.get('hook', '0x' + '0' * 40))
            if active:
                flags.add('hook_permissions_require_behavior_review')
            if any('ReturnsDelta' in name for name in active):
                flags.add('custom_accounting')
            if fee == 0x800000:
                flags.add('dynamic_fee')
            difference = abs(observed - reference)
            passed = difference * 10000 <= reference * tolerance
            hop_results.append({'token_in': token_in, 'token_out': token_out,
                'amount_in': str(amount_in), 'reference_out': str(reference),
                'observed_out': str(observed), 'absolute_difference': str(difference),
                'quote_matches': passed, 'hook_permissions': active})
            previous = token_out, observed
        minimum_passed = previous[1] >= minimum
        results.append({'id': name, 'passed': minimum_passed and all(h['quote_matches'] for h in hop_results),
                        'minimum_out_passed': minimum_passed, 'review_flags': sorted(flags), 'hops': hop_results})
    canonical = json.dumps(document, sort_keys=True, separators=(',', ':'), ensure_ascii=True).encode()
    return {'schema_version': 1, 'input_sha256': hashlib.sha256(canonical).hexdigest(),
            'passed': all(row['passed'] for row in results), 'routes': results, 'limitations': LIMITATIONS}


def markdown(report):
    rows = ['# Uniswap v4 quote replay receipt', '', f"Input SHA256: `{report['input_sha256']}`", '',
            '| Route | Quote / minimum-out checks | Review flags |', '|---|---|---|']
    for row in report['routes']:
        rows.append(f"| {row['id']} | {'PASS' if row['passed'] else 'FAIL'} | {', '.join(row['review_flags']) or 'none identified'} |")
    return '\n'.join(rows + ['', '## Scope and limitations', ''] + ['- ' + s for s in LIMITATIONS]) + '\n'
