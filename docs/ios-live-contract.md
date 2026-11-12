# What the live contract test found

The app is a client of the SuperCraftOS control center. A field that is renamed,
dropped, or changes type on the server breaks a screen in the app, and nothing on
the server notices. Two tests now guard that boundary from both sides.

| Test | Where it runs | What it proves |
| --- | --- | --- |
| `test_ios_backend_contract.py` | the VPS, against the live backend | Every live response satisfies the decoding contract of the Swift models |
| `LiveBackendContractTests` | the iOS Simulator, against the live backend | The app's own models decode the live responses |

The contract is written from the Swift `CodingKeys` in
`ios_app_dist/AppConfig.swift`. Change a model and the contract has to change
with it.

## The interaction layer

Decoding is not using. A model can fit the payload perfectly while the screen
that shows it is empty, and the button that fills it does nothing. Three more
layers drive the product rather than draw it.

| Test | Where it runs | What it does |
| --- | --- | --- |
| `ScreenInteractionTests` | the iOS Simulator, against the live backend | Drives the app's own `BackendStore` and asserts every one of the eight screens has live data behind it, that the Product Lab interprets a brief, that a workflow can be started, and that a broken address is reported rather than swallowed |
| `KeyboardInteractionTests` | the iOS Simulator, against the live control center | Fires **every** action tile through the extension's own `KeyboardBackend`, with the same query the keyboard builds when a user taps it, and asserts each one comes back with a real answer. The link tiles are checked for the right service, the Fn tiles for the exact combination and the two word description, and the catalogue for the eight tabs, the twelve tiles, the single large card and the badge palette |
| `SuperCraftOSUITests` | the iOS Simulator, against the live control center | Opens every screen by tapping it, switches all four visualisation modes, reads the live runtime state out of the header, types a request into the composer and sends it to the agent, opens the connection sheet and opens a workflow from the list |

The UI test runs on an iPad simulator when one is available, because the
control surface puts all eight screens in a sidebar there and every screen is
then one tap away rather than a scroll.

## Defects it found

### 1. The app threw away the reason the backend gave it

The backend answers a rejected request with a precise reason, for example
`unsupported_or_invalid_design_brief` with a detail. The app decoded nothing and
replaced it with `The backend rejected the request (HTTP 400)`.

`BackendStore` now decodes the error body and shows the reason, and the product
endpoints return the specific reason they rejected a request. The keyboard does
the same, so an AI tile that fails explains itself.

### 2. The interpreter could propose a design its own screener rejected

The prompt that asks the model for a design brief did not state the geometric
rules, so the model could return dimensions the screener then refused. The rules
are now in the prompt, and the interpreter retries once with the rejection
reason.

### 3. A 3 mm badge plate was not a valid design

The height floor was 5 mm for every template, so an ordinary thin plate was
rejected. The floor is now template aware: a plate may be 1 mm, an enclosure or a
bracket may not. A thin enclosure is still refused, and the refusal explains
itself.

### 4. The product lab stopped working for good

The design workspace grew until it reached its 100 design limit, and from then
on every product build failed. There was no way to reclaim space. The oldest
workspaces are now pruned automatically, keeping the twenty most recent, so the
product lab keeps working instead of failing permanently.

## Running it

```bash
.venv/bin/python -m unittest -q test_ios_backend_contract.py
```

The simulator test runs as part of the Bitrise pipeline, in the
`Run the keyboard tests and render the UI on the simulator` step, against
`https://agent.commetai.ca`.
