# Agent instructions and memory

The autonomous runtime ships its own instructions in `agent_runtime.py`. It does
not depend on a private agent implementation or an untracked skills checkout.
Its workflow is plan, act, observe, repair, verify and deliver, with actual file
and command evidence recorded separately from model claims.

`job_store.py` retains bounded lessons from completed tasks. Later prompts treat
lessons, source files and tool results as reference data. Specialist review is a
bounded additional model call, not a claim that a separate worker executed tests.

The older LangGraph artifact workflow can optionally read four bounded skill
files from `agent-brain/skills/` when the operator has installed that external
registry. A missing registry is supported. The public task runner requires no
such checkout and does not claim those external skills were installed.

No model weights are trained or copied by this repository.
