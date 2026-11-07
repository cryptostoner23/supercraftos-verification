# SuperCraftOS — Device UI-Driver E2E Suite (Revyl)

Human-like interaction through the real iOS interface only. No API shortcuts.
Each journey is a sequence of `revyl device` instructions (tap/type/screenshot/
validation) that a person would perform. Covers every module, screen, and
transition, exercising genuine high-difficulty tasks.

Session env: `REVYL_API_KEY` + `-s <session_id>`.

---

## 1. App launch & connection
- Instruction: "Accept any permissions. Wait for home screen. If the top-right
  shows a Connect banner, tap it, enter access key `BCQMChP-tCaOWU_aeLlY32rn618HAX3F8Oi4dIf0wjg`
  and URL `https://agent.commetai.ca`, then tap Save and connect."
- Validation: device shows "CONNECTED" or "SC / OS".

## 2. Mission / Home
- Tap Home tab. Validate the mission conversation area is present and interactive.

## 3. Digital Me — full lifecycle
- Open **Digital Me** (sidebar/More).
- Validation: identity card shows name + memory entry count.
- Type a memory in the add field, tap Save. Validate it appears in the list.
- Tap back; reopen; confirm persistence.

## 4. Apple Notes — import + manage
- Open **Notes**.
- Tap **Import all my Notes** → in the document picker, drill into an exported
  `.txt`/`.rtf`/`.html` file (or use the share extension) and select it.
- Validate the note appears in the list.
- Open it, edit the body, save, and verify the update.
- Pin it; verify the pinned indicator toggles.

## 5. Tasks — submit autonomous task (difficulty 9.5)
- Open **Tasks** → tap **+ New task**.
- Compose: "Build a Python script `collatz.py` that prints the Collatz
  sequence for an integer argument; attach output and prove it runs."
- Tap **START AUTONOMOUS TASK**.
- Wait for completion; open the task detail and validate delivered files +
  command output are present (not just an acceptance list).

## 6. Tasks — cancel/retry transition
- Submit a task, immediately test Cancel. Validate state transitions.
- Retry a completed task; validate a new run begins.

## 7. Memory / Learning
- Open **Memory**. Validate playbooks and lessons render from completed tasks.

## 8. Workflows
- Open **Workflows**. Validate durable plans/checkpoints/artifacts list loads.
- Create a workflow from a query; approve/deny a pending gate if present.

## 9. Funding / Grant Ops
- Open **Funding**. Validate catalog loads.
- Fill the project profile (name, summary, use-of-funds, budget) and tap
  **Screen funding fit**; validate results rows appear.
- Draft an application; validate a draft object persists.

## 10. Build / Product Lab
- Open **Build**. Enter dimensions and validate a design spec is interpreted.
- Run Screen/Interpret/Build; validate a 3D analysis/report appears
  (where CAD is available).

## 11. Engine / Platforms
- Open **Engine**. Validate the capability catalog renders.

## 12. Integrations
- Open **Integrations**. Validate the provider list loads with health status.

## 13. Tools
- Open **Tools**. Search and open a tool; validate its input panel loads.
- Run `gmail_status`; validate it reports connected.
- Run `gmail_read`; validate inbox messages render.

## 14. Accounts / Registrations
- Open **Accounts**. Validate account/verification status rows render.

## 15. Quests
- Open **Quests**. Validate sources/leads load; run a screen/action where available.

## 16. Shortcuts
- Open **Shortcuts**. Validate the hub renders; trigger one shortcut.

## 17. Search & nav transitions
- Use the search field on Workflows/Integrations/Tools/Accounts; validate filtering.
- Navigate across all tabs forward/back; validate no screen breaks.

## 18. Connection screen re-entry
- Open settings/Connection; validate fields prefill; cancel without breaking state.

## 19. Keyboard extension (if embedded)
- Long-press a text field, switch to the SuperCraftOS keyboard; validate it types.

## 20. Background/foreground
- Home button → reopen app; validate state restored without reconnect prompt.

## 21. Offline/error path
- (Optional) toggle network off via device; validate a graceful offline message.

## 22. Data persistence
- Relaunch the app; validate Digital Me memory, notes, and tasks persist.

## 23–25. Regression re-run
- Re-run journeys 3, 4, 5 after all others to confirm no regression.

---

## Execution commands (per journey)
```
REVYL_API_KEY=... revyl device instruction -s <session> "<step>"
REVYL_API_KEY=... revyl device validation -s <session> "<expected outcome>"
REVYL_API_KEY=... revyl device screenshot  --session-id <session> --out /tmp/<n>.png
```
Every journey ends with a `validation` (user-visible outcome) before moving on.
