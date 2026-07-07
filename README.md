# sabnzb-cli

A lightweight command-line dashboard for monitoring a [SABnzbd](https://sabnzbd.org)
instance from your terminal. Run `sab` for a live, full-screen view: current
status, a download-speed graph that fills the window, the active queue with
progress bars, and recent history — refreshing in place. You can pause/resume and
delete jobs from the keyboard, and add a `.nzb` by dragging it straight onto the
terminal.

```
┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
┃  SABnzbd Monitor                   192.168.1.10:8080          ● DOWNLOADING   ↓ 12.4 MB/s┃
┗━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┛
╭───────────────────────────────────── Download speed ─────────────────────────────────────╮
│ ▆▆▇▇█████▇▇▆▆▅▅▅▅▅▅▆▆▇▇█████▇▇▆▆▅▅▅▅▅▅▆▆▇▇████▇▇▇▆▅▅▅▅▅▅▆▆▇▇█████▇▇▆▆▅▅▅▅▅▅▆▆▇▇█████▇▇▆▆ │
│                                                                                          │
│ now 8.7 MB/s   peak 12.7 MB/s      disk [██████████░░░░░░] 180/465 GB (61% used)         │
╰──────────────────────────────────────────────────────────────────────────────────────────╯
╭─────────────────────────────────────── Queue (2) ────────────────────────────────────────╮
│       #  Name                 Size  Progress                           ETA  Status       │
│       1  Some.Big.Rele…    5.96 GB  ████████████░░░░░░░░░░  54%    0:06:12  Downloading  │
│       2  Another.Pack.…    3.12 GB  ███░░░░░░░░░░░░░░░░░░░  12%    0:18:40  Queued       │
╰──────────────────────────────────────────────────────────────────────────────────────────╯
```

## Install

Requires Python 3.9+ and git. The quickest way is the one-line installer, which
clones the project into `~/.sabnzb-cli`, sets up a self-contained virtualenv, and
puts the `sab` command on your PATH:

```sh
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/elliott99ukhb/sabnzb-cli/master/install.sh)"
```

Re-run the same command any time to update to the latest version. To uninstall:

```sh
bash ~/.sabnzb-cli/install.sh --uninstall
```

This removes the install and the `sab` / `sabnzb-cli` links but keeps your config.
Add `--purge` to also delete `~/.config/sabnzb-cli`.

### Other options

Install globally with [pipx](https://pipx.pypa.io):

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
   sab --init
   ```

   This writes a template to `~/.config/sabnzb-cli/config.json`. Edit it:

   ```json
   {
     "host": "192.168.1.10",
     "port": 8080,
     "apikey": "YOUR_API_KEY_HERE",
     "https": false,
     "SABNZBD_ACCESS_CLIENT_ID" : "xxxxx", #optional
     "SABNZBD_ACCESS_CLIENT_SECRET" : "xxxxx" #optional
   }
   ```

Settings are read from the first config file found, in this order:

1. `--config <path>`
2. `./config.json` in the current directory
3. `~/.config/sabnzb-cli/config.json`

The environment variables `SABNZBD_HOST`, `SABNZBD_PORT`, `SABNZBD_APIKEY` and
`SABNZBD_HTTPS` then override any matching values (and can supply them on their
own if you'd rather not use a file). If your SABnzbd sits behind Cloudflare
Access, set `SABNZBD_ACCESS_CLIENT_ID` and `SABNZBD_ACCESS_CLIENT_SECRET` too.

> **Note:** `config.json` contains your API key and is git-ignored. Never commit it.

## Usage

Run `sab` with no arguments for the interactive full-screen dashboard
(when run in a real terminal). Keyboard controls:

| Key | Action |
|-----|--------|
| `↑` / `↓` (or `k` / `j`) | Move the selection through the queue |
| `p` | Pause / resume the **selected** item |
| `d` | Delete the selected item (asks `y`/`n` to confirm) |
| `P` or `space` | Pause / resume the **whole** queue |
| `a` | Add a `.nzb` — opens an inline field: **drag a file onto the terminal** or type a path/URL, then `Enter` to add (`Esc` to cancel) |
| `r` | Refresh now |
| `q` | Quit |

Other commands and flags:

```sh
sab                        # interactive dashboard (q to quit)
sab add show.nzb           # upload a .nzb from this machine
sab add https://host/x.nzb # add from a URL
sab add /mnt/raid/x.nzb    # a path on the SABnzbd server itself
sab add a.nzb b.nzb --cat tv --priority high
sab pause / resume         # control the whole queue in one shot
sab --once                 # print a single snapshot and exit (good for scripts)
sab -i 2                   # refresh every 2 seconds
sab --no-history           # hide the recent-history side panel
sab --no-interactive       # live view without keyboard control
sab --config ./my-config.json
sab --version
```

(`sabnzb-cli` is installed as an alias for `sab`, so either name works.)

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
