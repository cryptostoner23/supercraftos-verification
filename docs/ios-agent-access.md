# Reaching the agent from the iOS app

The iOS app is the control surface for the SuperCraftOS agent system. It has to
be able to reach the agent from wherever the phone can, and switch between
hosts without retyping anything.

## Bookmarks

**Connection** in the app now keeps a list of saved agent endpoints.

- Type an address, tap **Save this endpoint**, and it is remembered.
- Tap a saved endpoint to connect to it. The check mark shows which one is
  live.
- Swipe a saved endpoint to delete it.
- Each entry is labelled **LOCAL NETWORK** or **PUBLIC**, so you can see at a
  glance which one is a LAN address and which one goes out to the internet.

The list is stored on the device only. Nothing about your endpoints leaves the
phone.

## Local network access, no VPN and no mesh

The app and the keyboard accept a **private address over plain HTTP**, and
the backend accepts a private `Host` header. That means the phone can reach
the agent on the local network, with no internet connection, no VPN and no
mesh tunnel, and still work.

| Address | Allowed | Meaning |
| --- | --- | --- |
| `https://agent.commetai.ca` | yes | The public endpoint |
| `http://192.168.1.50:8787` | yes | The agent on your LAN |
| `http://127.0.0.1:8787` | yes | The agent on the phone itself, or a local tunnel |
| `http://10.0.0.7:8787` | yes | Private range |
| `http://172.16.4.2:8787` | yes | Private range |
| `http://169.254.1.1:8787` | yes | Link local |
| `http://macbook.local:8787` | yes | Bonjour name |
| `http://agent.commetai.ca` | **no** | A public host must use HTTPS |

The rule lives in one place, `BackendEndpointPolicy` in the shared catalog, and
the app and the keyboard both use it, so they can never disagree about which
endpoint they are allowed to talk to.

App Transport Security is configured with `NSAllowsLocalNetworking` on both
the app and the keyboard extension, which is what allows plain HTTP to a local
address at all. Public hosts still require HTTPS.

## What the backend changed

`supercraftos_cli.py` now accepts a private `Host` header in addition to
`127.0.0.1`, `localhost` and `::1`. The server only ever binds to loopback, so
it is always reached through a local proxy; a proxy on the LAN presents the
machine's private address, and that now works.

Public hostnames are still rejected with a 403. The check is:

```python
hostname in {"127.0.0.1", "localhost", "::1"} or is_private_host(hostname)
```

where `is_private_host` accepts private, loopback and link-local addresses,
and `*.local` names.

## The agent, reachable from the phone

With the public endpoint in place, the phone talks to the same agent the
dashboard and the MCP server use:

- `GET /api/session` opens a control session and returns the token.
- `POST /api/workflows` runs the agent, with `X-SuperCraftOS-Token`.
- The rest of the surface the app uses, `/api/status`, `/api/tools`,
  `/api/workflows`, `/api/integrations`, `/api/registrations`,
  `/api/capabilities`, `/api/grants/catalog`, `/api/products/*`, all work
  identically over a LAN address.

The keyboard uses the same two calls, so the AI tiles work from a local
address exactly as they do from the public one, as long as the extension was
built with that address.
