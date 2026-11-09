# Grant portal registration and application requirements

Research date: 2026-10-19. This map uses the official programme pages and does not create accounts or submit applications.

## Ethereum Foundation Ecosystem Support Program (ESP)

- Official applicant process: https://esp.ethereum.foundation/applicants
- Entry: browse a matching Wishlist or RFP item, then submit an application. The application should describe the applicant's background and approach, methodology, timeline, and deliverables. The page does not publish a general public API or machine-readable submission endpoint.
- Eligibility and fit: work that improves Ethereum's foundations; supported work is open-source, non-commercial grant-funded output, and aligned with censorship resistance, open source, privacy, and security. Evaluation covers technical approach, ecosystem impact, openness, budget, experience, and alignment.
- After application: confirmation email; review may include interview, rescoping, and budget negotiation. Most reviews are listed as 3–6 weeks.
- If selected: milestone-based grant structure; payments are on-chain in ETH by default, so the recipient needs a secure ETH receiving wallet. Every recipient completes onboarding with identity verification and a formal grant letter. The official page does not enumerate the identity documents or expose a public application API; expect the grant team to provide those after selection.
- Automation surface: official web application only as documented; no public submission API found. An agent can prepare the requested methodology, timeline, deliverables, budget, wallet field, and evidence, but should not invent undocumented fields.

## Gitcoin Grants

- Programme: https://gitcoin.co/program
- Builder entry: https://builder.gitcoin.co/
- Official FAQ: https://grants.gitcoin.co/faqs
- Application model: create one Grants Stack Builder profile and apply to each eligible round. A specific round determines its eligibility, fields, dates, and onboarding requirements. The programme page describes an application period, review, crowdfunding, and distribution after Sybil checks.
- Typical profile inputs: project identity and summary, grant description/TL;DR, why the work matters, use of funds, round tags/fit, technical/project links, and a receiving wallet/payment destination as required by the round. Gitcoin's official tips advise applying early and explaining the problem, intended spend, relevance, and round fit.
- KYC: the official support page says grantees receiving more than $15,000 in matching funds (or certain sponsored rounds) may need KYC. For an individual, listed requirements include full name, physical address, government ID, proof of address, and SSN for US citizens. For a corporation: legal name, physical address, proof of address, and proof of incorporation. The KYC process is communicated by email and is separate from ordinary profile creation.
- Identity/trust: round-specific requirements can include Gitcoin Passport or other verification. Do not treat historical trust-score pages as current round requirements; check the selected round's official instructions.
- API: Gitcoin Grants Stack has public/open-source APIs and protocol components, but no universal public API was identified in the official programme pages for creating/submitting every current Builder application. Use the round's documented Builder flow or an approved integration; preserve the round ID and submission receipt.

## Arbitrum Foundation Grants

- Official grants directory: https://arbitrum.foundation/grants
- Current directory status is dynamic. The page currently lists an Alchemy–Arbitrum Grant Program as active (Orbit development, up to $500,000 in Alchemy infrastructure credits, application link to https://alchemyapi.typeform.com/) while several Foundation/DAO programmes are marked inactive or coming soon. Recheck status before drafting or submitting.
- Current Foundation grant description: dApps and Infrastructure & Tools; milestone-based funding; applications are approved on a rolling basis when the programme is open. The page links the official application information/application form through Arbitrum Foundation's Notion pages.
- Common application fields: project/team identity, problem and solution, chain deployment and ecosystem alignment, development stage, milestones, timeline, requested budget/funding use, links to repository/demo/metrics, and contact details. The official programme page does not expose a universal submission API.
- DAO route: https://forum.arbitrum.foundation/ and official governance how-to https://docs.arbitrum.foundation/how-tos/create-submit-dao-proposal. A DAO funding proposal is different from a Foundation grant application and requires a forum proposal; on-chain proposals have wallet and voting-power prerequisites.

### Arbitrum Audit Subsidy Program

- Official application process: https://forum.arbitrum.foundation/t/arbitrum-audit-program/28368
- Required information: team names/background/notable investors; project overview/problem, product-market-fit evidence, development stage and mainnet timeline; audit scope, lines of code and languages, desired completion date; preferred auditor (optional); and audit budget request.
- Eligibility: auditable smart contracts (Solidity or Stylus), early-stage or materially upgraded code, native or migrating Arbitrum deployment, new audit, Arbitrum ecosystem launch, and an exclusivity period. The audited code must remain exclusive to Arbitrum for the fixed period in the programme terms.
- Commercial terms: subsidy is paid to the auditor after completion; the applicant pays a negotiated portion. Due diligence and committee review can include code and references. The application is described as an open track with a standardised form; no public API is documented.

## Optimism mission funding

- Current governance forum: https://gov.optimism.io/
- Historical Atlas mission page (the page states Atlas is discontinued on 2026-09-18): https://atlas.optimism.io/missions/governance-fund-missions
- Mission route: read the Mission Request post in the Optimism Governance Forum and complete the form embedded in that post as a comment. Each mission has its own deadline and eligibility/chain scope.
- If selected: the Foundation contacts the winner; the recipient undergoes KYC and signs a grant agreement; the grant is delivered to a locked multisig within one week of KYC completion and agreement signature (per the mission page).
- Required inputs vary by mission. The agent should extract the exact form questions, supported chains, budget, deadline, milestones, impact metrics, team/project evidence, and wallet or multisig details from the specific official Mission Request post.
- API: no public API for submitting arbitrary mission applications was identified. The documented interface is the forum post/comment form. Atlas should be treated as historical/transitioning; do not submit to the old Atlas URL without confirming the current Optimism forum route.

## Shared onboarding record to collect locally

The agent can request and securely store, server-side, the following user-owned profile fields before any application adapter runs: legal/applicant name, organization/legal entity (if any), contact email, public website, repository/demo links, biography/team evidence, project description, target chain(s), milestones and dates, requested amount and budget, payment wallet or multisig address, tax/entity documents when an official portal requests them, and links/evidence permitted for public disclosure. Sensitive identity documents should be entered only into the official programme's protected KYC flow, never copied into logs or proposal text unless the programme explicitly requires it.

## Automation conclusion

No official source reviewed here exposes one universal API that submits to every programme. The correct autonomous design is provider-specific adapters: discover and refresh official opportunities; extract the exact live form/schema; validate the local applicant profile against it; generate and submit through the programme's documented Builder, Typeform, forum, or official portal; retain request/receipt/status; and refresh stale links/status. This is a technical integration finding, not a blanket manual-approval rule.
