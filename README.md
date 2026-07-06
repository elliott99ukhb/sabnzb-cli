# sabnzb-cli

A lightweight command-line dashboard for monitoring a [SABnzbd](https://sabnzbd.org)
instance from your Mac terminal. It shows current status, a live download-speed
graph, the active queue with progress bars, and recent history — refreshing in
place.

```
┌ SABnzbd ─────────────────────────────────────────────────────────────┐
│ 192.168.1.10:8080    DOWNLOADING    ↓ 12.4 MB/s   remaining 4.20 GB   │
│ disk [████████████░░░░░░░░] 180.5 GB free of 465.0 GB (61% used)      │
└──────────────────────────────────────────────────────────────────────┘
┌ Download speed ──────────────────────────────────────────────────────┐
│ ▁▂▃▄▅▆▇█▇▆▅▆▇█▇▆▅▄▃▄▅▆▇█                                              │
│ now 12.4 MB/s    peak 14.1 MB/s                                       │
└──────────────────────────────────────────────────────────────────────┘
┌ Queue (2) ───────────────────────────────────────────────────────────┐
│ #  Name                 Size   Progress               ETA    Status   │
│ 1  Some.Big.Release…   6.1 GB  ████████░░░░░░░  54%   0:06:12 Downl…  │
└──────────────────────────────────────────────────────────────────────┘
```

## Install

Requires Python 3.9+. Install globally with
[pipx](https://pipx.pypa.io) so `sabnzb-cli` is on your PATH:

```sh
cd sabnzb-cli
pipx install .
```

Or in a virtualenv for development:

```sh
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
```

## Configure

1. In SABnzbd, go to **Config → General → API Key** and copy your API key.
2. Create a config file. The quickest way:

   ```sh
   sabnzb-cli --init
   ```

   This writes a template to `~/.config/sabnzb-cli/config.json`. Edit it:

   ```json
   {
     "host": "192.168.1.10",
     "port": 8080,
     "apikey": "YOUR_API_KEY_HERE",
     "https": false
   }
   ```

Config is resolved in this order (first match wins), with any of the
environment variables filling in the gaps:

1. `--config <path>`
2. `./config.json` in the current directory
3. `~/.config/sabnzb-cli/config.json`
4. `SABNZBD_HOST`, `SABNZBD_PORT`, `SABNZBD_APIKEY`, `SABNZBD_HTTPS`

> **Note:** `config.json` contains your API key and is git-ignored. Never commit it.

## Usage

Run `sabnzb-cli` with no arguments for the interactive full-screen dashboard
(when run in a real terminal). Keyboard controls:

| Key | Action |
|-----|--------|
| `↑` / `↓` (or `k` / `j`) | Move the selection through the queue |
| `p` | Pause / resume the **selected** item |
| `d` | Delete the selected item (asks `y`/`n` to confirm) |
| `P` or `space` | Pause / resume the **whole** queue |
| `a` | Add a `.nzb` — prompts for a file path or URL |
| `r` | Refresh now |
| `q` | Quit |

Other commands and flags:

```sh
sabnzb-cli                 # interactive dashboard (q to quit)
sabnzb-cli add show.nzb            # upload a .nzb from this Mac
sabnzb-cli add https://host/x.nzb  # add from a URL
sabnzb-cli add /mnt/raid/x.nzb     # a path on the SABnzbd server itself
sabnzb-cli add a.nzb b.nzb --cat tv --priority high
sabnzb-cli pause / resume  # control the whole queue in one shot
sabnzb-cli --once          # print a single snapshot and exit (good for scripts)
sabnzb-cli -i 2            # refresh every 2 seconds
sabnzb-cli --no-history    # hide the recent-history side panel
sabnzb-cli --no-interactive  # live view without keyboard control
sabnzb-cli --config ./my-config.json
sabnzb-cli --version
```

Valid `--priority` values: `default`, `low`, `normal`, `high`, `force`, `paused`.

**How `add` chooses what to do:** a URL is fetched by SABnzbd; a path that
exists on *this* machine is uploaded; any other path is passed to SABnzbd as a
path on *its own* filesystem (`addlocalfile`). For that last case the file must
be readable by the SABnzbd server process.

## How it works

It talks to SABnzbd's JSON API (`?mode=queue` and `?mode=history`) and renders
the result with [`rich`](https://rich.readthedocs.io). The only dependencies are
`rich` and `requests`.

## License

MIT
