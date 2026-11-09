# Verified grant and agent-payment interfaces

Checked 2026-10-19 against first-party sources. An application form, a grants
protocol, and an x402 payment endpoint are distinct interfaces. The presence of
one does not establish the behavior of another.

| Program or protocol | Verified interface | Current SuperCraftOS handling | Source |
| --- | --- | --- | --- |
| Arbitrum Audit Program | Five-page Tally application | Direct URL and `tally_form` classification; no completed submission receipt | [Arbitrum grants](https://arbitrum.foundation/grants), [application](https://tally.so/r/3xzEzv?program=aap&ref=blog.arbitrum.foundation) |
| ArbiFuel | Airtable application form | Direct URL and `airtable_form` classification; no completed submission receipt | [Arbitrum grants](https://arbitrum.foundation/grants), [application](https://airtable.com/appzb4GfqGfrnDXjW/shrulGIIp6l6ezAlt) |
| Alchemy-Arbitrum | Typeform application form | Direct URL and `typeform` classification; no completed submission receipt | [Arbitrum grants](https://arbitrum.foundation/grants), [application](https://alchemyapi.typeform.com/to/CijtV0Oe) |
| Gitcoin Grants | Grants Stack Builder and Allo protocol round registration | `allo_protocol` classification and official integration source; no onchain transaction receipt | [Gitcoin Grants Stack](https://github.com/gitcoinco/grants-stack), [Allo starter kit](https://github.com/gitcoinco/allo-starter-kit), [Allo protocol](https://github.com/allo-protocol/allo-v2) |
| x402 | HTTP payment negotiation and settlement for paid services | Agent commerce research reference; no claim of grant submission | [Coinbase x402](https://www.coinbase.com/developer-platform/discover/launches/x402) |
| Circle Developer Grants | Circle's active grant intake at Questbook; milestone-based USDC grants include agentic economy use cases | Official portal and `grant` classification; submission receipt still required | [Circle program](https://www.circle.com/grant), [Circle intake](https://circle.questbook.app/) |
| Uniswap Foundation Grants | Official foundation grant program and HubSpot application | Direct form URL classified as `hubspot_form`; no completed submission receipt | [Uniswap build](https://www.uniswapfoundation.org/build), [application](https://share.hsforms.com/1fxQjPQTgTYmPwlYxxKlSGQsdca9) |
| Base Ecosystem Fund | Pre-seed and seed investment application | Classified as `equity_investment`, not a grant | [Base fund](https://www.base.org/ecosystem-fund), [application](https://www.base.org/ecosystem-fund/apply) |
| Robinhood Chain / Arbitrum Open House | Robinhood committed $1 million to 2026 Open House developer activity | Monitored as a dated sponsorship; no standing intake claimed | [Robinhood announcement](https://robinhood.com/newsroom/robinhood-chain-launches-public-testnet/) |
| Virtuals EconomyOS | GitHub-linked inference and compute credits; discretionary review form | Classified as `infrastructure_credits`, not cash grant | [Virtuals program](https://os.virtuals.io/community), [review form](https://virtualsprotocol.typeform.com/to/BwtdGEAL) |
| 1inch Fusion resolver | Self-service resolver registration in Business Portal, contract verification and order access | Classified as `commercial_protocol_opportunity`, not a grant | [1inch resolver onboarding](https://business.1inch.com/portal/documentation/resolvers/introduction), [self-service announcement](https://business.1inch.com/whats-new/resolver-self-service-onboarding) |

See [the broader funding inventory](funding-sources.md) for startup credit programs and application prerequisites. Program pages can change; the checked date above is the observation date, not a promise of continued availability.

Typeform documents a Responses API for retrieving and deleting responses, not
a public respondent submission endpoint; see its [API reference](https://developer.typeform.com/developers/get-started/scopes/).
Airtable's [Web API](https://support.airtable.com/articles/6292134965-getting-started-with-airtable-s-web-api)
can create records in bases to which the API principal has access. That does not
give an applicant write access to the grant operator's base.

The generic `SUPERCRAFTOS_GRANT_ENDPOINT_<PROGRAM_ID>` adapter only sends to an
explicitly configured HTTPS host from the program record. It is not evidence
that the program offers a JSON intake. `unsupported` means no authenticated
adapter ran; it does not mean the program lacks an application interface.
