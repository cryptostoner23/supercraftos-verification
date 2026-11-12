# Uniswap v4 quote replay receipt

Input SHA256: `59f1ac08baee1650be6bcd945bf275dc9ae1e4115f2e272d9a8bf2aabaac81f9`

| Route | Quote / minimum-out checks | Review flags |
|---|---|---|
| single_exact | PASS | none identified |
| multi_hop | PASS | none identified |
| hook_dynamic | PASS | custom_accounting, dynamic_fee, hook_permissions_require_behavior_review |

## Scope and limitations

- Compares supplied reference and observed quotes; it does not independently simulate PoolManager.
- Fixtures are reproducible test vectors, not live prices or evidence of profitable execution.
- Hook flags identify callable permissions, not an audit of contract behavior.
- No RPC, private keys, signatures, transactions or blockchain database are needed.
