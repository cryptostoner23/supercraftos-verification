# Quest, rewards, and chain-launch source map

Checked 2026-10-19. These are discovery and participation leads, not verified earnings. A testnet faucet's tokens have no monetary value; points, raffle entries, and quests do not guarantee a later airdrop. Each candidate needs its own current official campaign page, dates, eligibility, reward terms, and authenticated route before execution.

| Source | What the official source exposes | Agent route and important distinction |
| --- | --- | --- |
| [Galxe Quest Explore](https://app.galxe.com/quest/explore/all) and [Galxe Quest product](https://www.galxe.com/quest) | Live quest discovery with filters for gas-free, airdrop, recurring, onchain activity, reward type, ecosystem, and status. | Discover and classify via public pages; an individual quest supplies its tasks and reward rules. The product page documents creator-side API integrations, **not** a general participant claim API. Completion and claim normally require the signed-in user account and sometimes a connected wallet or other identity. Do not infer a public automated-claim endpoint. |
| [Layer3 Discover](https://app.layer3.xyz/discover) | Current public discovery surface offers New, Collections, Ecosystems, Campaigns and Streaks. It advertises Liquid Rewards and early-chain participation, with sign-up/login for account actions. | Discover and verify each campaign's requirements and reward terms. No public participant execution API was established; the account/wallet route is campaign-specific. |
| [Zealy Explore](https://www.zealy.io/explore), [list quests API](https://docs.zealy.io/api-reference/quests/list-quests), [claimed-quests lookup](https://docs.zealy.io/api-reference/reviews/claimed-quests-lookup) | Community discovery and authenticated **community-admin** quest/review APIs. The list endpoint explicitly requires an admin API key. | Use public Explore for leads. The documented API is for operators of their own community, not a participant API for claiming quests in unrelated communities. Reward and review state must be checked on each campaign. |
| [Intract community hub](https://docs.intract.io/product-guide/getting-started/community-hub-overview), [API task integration](https://docs.intract.io/product-guide/tools-guides/integrate-apis), [reward policy](https://docs.intract.io/faq-and-troubleshooting/reward-policy) | Quest and loyalty infrastructure. Creator-side API verifies participant actions; rewards can be points, tokens, NFTs, codes, or raffles. Some rewards are manually distributed by a project. | Discover campaign pages and verify each project's rules. An Intract verification API is called **by Intract against the project's API**; it is not a participant submission/claim API. |
| [CoinList testnet/rewards listings](https://coinlist.co/help/where-can-i-learn-more-about-flow?locale=en), [CoinList testnet announcements](https://blog.coinlist.co/tag/testnets/) | Project testnet and reward campaign leads; each announcement has its own eligibility, window, task and payout terms. | Track announcements, follow the linked current campaign, and record account/KYC/wallet prerequisites. A historical CoinList post is evidence that a program existed, not evidence that it is open now. [CoinList's testnet guide](https://blog.coinlist.co/how-to-structure-your-incentivized-testnet/) notes eligibility checks and reward distributions may be project-specific. |
| [Ethereum Foundation protocol announcements](https://blog.ethereum.org/category/protocol), [Solana changelog](https://solana.com/changelog) | First-party testnet and protocol launch notices; useful to detect genuine network changes. | These are authoritative discovery/verification inputs, but a protocol testnet announcement itself is **not** an incentivized quest or token airdrop. Confirm incentives separately with the project's official campaign terms. |
| [Solana cluster reference](https://solana.com/docs/references/clusters) and [testnet faucets](https://solana.com/developers/cookbook/development/airdrops-and-faucets) | Public devnet/testnet endpoints and faucets. | Development test tokens are not cash or investment returns. Faucet requests are a legitimate programmatic testnet action, subject to rate limits, but do not count as a reward claim. |

## Bloomberg News access

[Bloomberg Developer](https://developer.bloomberg.com/) requires sign-in for API documentation. Bloomberg's [Enterprise Console](https://console.bloomberg.com/about/1935) provisions application credentials **after** API access has been granted; its [Web API policy](https://console.bloomberg.com/about/82) describes JWT/OAuth and registered IP addresses. [Data License](https://professional.bloomberg.com/products/data/data-license/) can include News through contracted REST/SFTP/cloud delivery. No Bloomberg license or API entitlement has been verified for this project, so do not label a public Bloomberg page scrape as an authorized Bloomberg News feed or claim Bloomberg coverage is currently active. The agent can ingest Bloomberg via the licensed feed once provisioned; until then, use first-party foundation/project announcements and their public pages for leads.

## Execution model

An autonomous agent can poll or subscribe to the public discovery sources, normalize title/source URL/published time/campaign close time, deduplicate by canonical URL, and cross-check a candidate against the project's official announcement and live campaign terms. It can rank opportunities by chain, estimated effort, actual reward type, deadline and eligibility, and perform task steps for which it has an authenticated and documented interface. Persist each external action's result and receipt. For quests requiring a platform account, KYC, wallet signature, social proof, or a project-specific review, report the exact required step and resume automatically after that prerequisite exists; do not manufacture proof or equate a submitted task with a paid reward. These sources alone do **not** show a universal participant API that could truthfully complete every Galxe, Zealy, Intract, or CoinList campaign.

### Configuring an execution adapter

Discovery works with no configuration. Actually running a quest needs an
authenticated route into the provider, and none of the sources above publish a
general participant claim API, so an adapter is per provider and per
programme:

```sh
SUPERCRAFTOS_QUEST_EXEC_ENDPOINT_<PROVIDER>   # HTTPS URL on the provider's own host
SUPERCRAFTOS_QUEST_TOKEN_<PROVIDER>            # Bearer credential for that endpoint
```

The provider is the source's `provider` field, uppercased: `GALXE`, `ZEALY`,
`BLOOMBERG`. The endpoint must be an HTTPS URL on a host the provider already
publishes, and the token must be a valid Bearer credential; anything else is
refused rather than called.

Note that Bloomberg is a news feed and not a quest, so it has no execution
adapter: an action on one of its leads is reported as `research_only`.

Without both variables, an action returns `adapter_unavailable` and the exact
reason. That is the honest answer: the agent discovered the quest and cannot
complete it, because nobody has configured the route that would let it.

The same rule applies to grants. `SUPERCRAFTOS_GRANT_ENDPOINT_<PROGRAM_ID>`
names an HTTPS intake for one programme, and the request only goes to a host
the programme's own record already lists. See
[the grant interfaces](grant-interfaces.md) for what each programme actually
exposes.
