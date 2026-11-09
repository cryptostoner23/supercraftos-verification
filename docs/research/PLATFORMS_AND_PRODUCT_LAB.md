# Agent platforms and physical-product engineering

Research checked 18 October 2026. Primary project documentation and repository metadata establish features, licenses and maintenance. Product Hunt, Hacker News and Reddit are used for discovery and reports of user friction, not as independent benchmarks. No current source establishes a universal best agent, a 10–20-year capability lead, or unlimited free access to commercial platforms.

## Product comparison and design decisions

| Platform | Useful capabilities | Hosting, price and license boundary | SuperCraftOS treatment |
|---|---|---|---|
| Meta Muse | Persistent personal context, dedicated browser VM, app connections, explicit sensitive-action controls | Meta-hosted; regional availability, free usage and paid plans. No self-hostable Muse implementation verified | Adopt continuity, audit and scoped permissions as native design patterns |
| Grok Bot | Persistent cloud desktop, specialist teams and shared website login context | Vendor-hosted; applicable account/plan required. Public code using Grok APIs does not grant the hosted service | Official sign-in access; isolate specialist responsibilities and expose action evidence |
| Manus | General execution, research, app connectors, custom MCP and API integration | Provider account/credits. Connector authorization happens in the provider's web app | Adopt typed connectors, durable execution and explicit authorization boundaries |
| OpenManus | Configurable agent loop, browser tools and MCP | MIT source; model/browser execution still needs resources and configuration | Research/catalog entry; do not confuse it with Manus or assume equivalent quality |
| OpenHands | Coding-agent control center, ACP-compatible agents, local/remote execution and automations | MIT core; runtime and inference costs remain. Inspect component terms | Strong candidate for a dedicated coding workspace with explicit sandbox boundary |
| LibreChat | Multi-user authentication, multiple model providers, agents, MCP and artifacts | MIT; separate model, storage and deployment resources | Strong candidate for a future self-hosted authenticated workspace; not installed by this change |
| Hermes Agent | Persistent memory, reusable skills and tool/messaging integration | MIT repository; local or remote inference has hardware/provider requirements | Candidate for experience-to-skill improvements; source catalog with official release metadata |
| MUSE research framework | Hierarchical experience memory and reflection | MIT research implementation; distinct from Meta's hosted Muse | Treat paper/repository results as author claims requiring task-specific replication |
| Dify | Visual workflows, RAG and model/tool integrations | Apache-derived Dify license adds conditions, including tenancy/branding concerns | Cataloged; review deployment terms before embedding a multi-user commercial service |
| Flowise | Visual agent/workflow composition | Current official repository is marked archived in the observed metadata | Retained as a research reference, visibly marked archived; not deployed as an actively maintained default |
| CadQuery / OpenCascade | Exact solids, parametric geometry and CAD interchange | Installed locally; no per-export API charge. Dependencies retain their own licenses | Native Product Lab export engine, version pinned and tested |
| Autodesk AutoCAD Web | Official web CAD editor | Proprietary subscription/entitlement | Official sign-in access; never presented as a free bundled AutoCAD license |

Primary references: [Meta Muse announcement](https://about.fb.com/news/2026/09/introducing-muse-personal-ai-agent/), [Grok Bot guide](https://x.ai/bot/guides/grok-bot-101), [Manus connectors](https://www.manus.im/features/connectors), [Manus API authorization](https://open.manus.im/docs/v2/connectors), [OpenManus source](https://github.com/FoundationAgents/OpenManus), [OpenHands source](https://github.com/OpenHands/OpenHands), [LibreChat source](https://github.com/LibreChat-AI/LibreChat), [Hermes source](https://github.com/NousResearch/hermes-agent), [MUSE research source](https://github.com/KnowledgeXLab/MUSE), [Dify license](https://github.com/langgenius/dify/blob/main/LICENSE), [Flowise releases](https://github.com/FlowiseAI/Flowise/releases/latest), [CadQuery exports](https://cadquery.readthedocs.io/en/latest/importexport.html), [AutoCAD Web](https://web.autocad.com/).

## What community research adds

- [Manus on Product Hunt](https://www.producthunt.com/products/manus) provides launch history and user reports. The page includes both praise for task completion and complaints about account/referral handling. This supports making account state and failure explanations visible; it is not proof that a particular agent is superior.
- [OpenHuman on Product Hunt](https://www.producthunt.com/products/openhuman) surfaced another open harness and user questions about privacy. It remains a discovery lead, not an installed or vetted dependency.
- [Hacker News discussion of agent swarms](https://news.ycombinator.com/item?id=44508250) questions whether adding agents itself improves unsupervised work. SuperCraftOS should measure completed tasks, recovery and cost rather than displaying agent counts as a quality claim.
- [Grok Bot community discussion](https://www.reddit.com/r/grok/comments/1w43c1v/grok_bots_own_docs_say_all_your_bots_share_one/) raises shared-computer/shared-login concerns. The vendor's own guide confirms shared login reach across bots; this is a reason to display permission boundaries clearly.
- [Hacker News CadQuery discussion](https://news.ycombinator.com/item?id=17038257) highlights the importance of visual design review, assembly context and ergonomics. Product Lab therefore combines a manipulable 3D view with editable parameters and exported solids instead of treating code generation as sufficient engineering.
- [CadQuery community practice](https://www.reddit.com/r/cadquery/comments/1gzi108/professional_use_of_cadascode/) is useful for workflow discovery. Professional suitability still needs inspection of the actual model, machine/process capabilities and tests.

These are qualitative signals from selected discussions, not a representative user study. Older discussions are explicitly not used to establish current release status. Current official maintenance evidence is saved in `repository-evidence.json` and `data/platform-releases.json`; failures or missing tagged releases remain explicit.

## Evaluation before selecting another agent engine

Run the same bounded workload against each candidate: a document task with citations; an authenticated connector task; a repository change with failing/passing checks; interrupted-task recovery; injected malicious instructions in retrieved content; and a design brief requiring rejection of unsupported geometry. Record success against acceptance criteria, artifacts, elapsed time, input/output tokens, actual provider charges, memory, permission prompts and recovery behavior. Keep model, budget and tool access comparable. No such cross-platform benchmark was run during this implementation, so the table is a capability/fit comparison, not a leaderboard.

The strongest reusable architecture is durable checkpoints plus evidence-linked memory, provider-independent routing, typed tool contracts, restricted execution, explicit connector consent and regression-tested upgrades. Multiple agents only help when their responsibilities and verification are measurable.

## Physical product pipeline implemented

1. Capture a design brief, dimensions, material/process and optional force.
2. Optionally ask the configured model to propose a specification within one of three supported templates. Unsupported concepts must be rejected. The returned JSON is validated; generated Python is never executed.
3. Adjust an open-top enclosure, mounting plate or L bracket in the live iOS 3D preview. The preliminary on-device preview omits holes; the final mesh is authoritative.
4. Screen wall/process conflicts, dimension bounds, nominal hole placement and missing evidence. Material constants and process screens are explicit assumptions, not supplier-certified properties.
5. Generate the exact solid with the OpenCascade kernel installed by CadQuery 2.8.0. The initial full CadQuery import exceeded the worker memory budget; direct use of its OCP kernel reduced the measured export worker to about 306 MB.
6. Check solid validity/count and positive volume; export STEP, STL and a bottom-face DXF profile. Re-import STEP and compare validity and volume. The DXF is not a fully dimensioned production drawing; STEP is not DWG.
7. Estimate fully dense mass from CAD volume and an assumed density. It excludes hardware, infill, supports, scrap and procurement costs.
8. For a solid hole-free plate only, optionally calculate the stated idealized rectangular-cantilever bending stress and deflection. Other load paths remain unknown; no general FEA result is invented.
9. Export artifacts and the screening report to Files/sharing for a slicer, CAD/CAM engineer or manufacturer. Make fit/material coupons, build a prototype and feed measured results into the next revision.

Real geometry is necessary but insufficient for a genuine product. The current engine cannot prove electronics feasibility, thermal behavior, fatigue, anisotropic print strength, certification, supply-chain availability, tolerances, assembly fit or business viability from an idea. Those items remain unresolved until the relevant analysis, supplier evidence and physical measurements exist. A candidate status means suitable for the next prototype investigation, not approved for manufacture or use.

## Installed features and update policy

`platform_registry.py` maintains 12 research entries and checks official repository release/archival metadata daily while the dashboard or `main.py run` is active. It caches checks and records failures; it does not silently replace running code. Archived projects stay visibly archived. The catalog is evidence for native design choices; it does not install or sign users into those external platforms.

The actual installed CAD dependency tree is isolated in `.cad-venv` and pinned in `requirements-cad.lock`. Product exports run one worker at a time, with a 384 MB RSS budget, 45-second wall deadline, CPU/file limits, bounded numeric inputs and fixed templates. The application never accepts arbitrary CAD Python. Daily release discovery is implemented; unattended source self-modification and automatic dependency promotion are not. An upgrade should use a separate environment, the same geometry/API regression checks, an atomic promotion and rollback, preserving design artifacts and credentials.

The Swift export remains two raw UTF-8/LF files and is repackaged as `YourApp.swiftpm`. Native SwiftUI/SceneKit rendering and provider sign-in still require Apple-platform verification. Linux checks verify syntax and portable logic, not Apple SDK compilation.

## Observed implementation evidence

- `data/audit/idea-to-product-live.json`: one real written brief passed the configured model via the public HTTP interpretation endpoint (200), then the CAD build endpoint (201). The resulting enclosure was 100 × 70 × 35 mm, volume 52,488 mm³, with valid solid topology and a successful STEP re-import.
- `data/audit/product-live-build.json`: standalone generation took 1.831 seconds; worker RSS peaked at 305.99 MB; nominal fully dense PLA mass was estimated as 65.085 g. These are measurements for this model and VPS, not performance guarantees.
- `data/audit/product-api-tests.log`: public API checks exercise finite/bounded/schema validation, process mismatch, a known analytical beam case, all three CAD templates, actual artifact downloads and path rejection. Tests make no model/paid-API calls.
- `data/audit/dxf-validation.json`: an independent DXF parser read all three latest template profiles, confirmed millimetre units and reported zero audit errors. This validates interchange structure, not fabrication tolerances.
- `data/audit/product-mcp-screen.json`: actual stdio MCP tool call returned the product screen. The local catalog now includes four built-in tools, including two design tools.
- `data/platform-releases.json`: actual official repository API checks retained latest tags or null when absent, maintenance timestamps, license identifiers and Flowise's archived state.
