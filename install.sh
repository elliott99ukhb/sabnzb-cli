#!/bin/bash
#
# sabnzb-cli installer
#
#   Install / update:
#     /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/elliott99ukhb/sabnzb-cli/master/install.sh)"
#
#   Uninstall:
#     curl -fsSL https://raw.githubusercontent.com/elliott99ukhb/sabnzb-cli/master/install.sh | bash -s -- --uninstall
#     # or, if already installed:  bash ~/.sabnzb-cli/install.sh --uninstall
#
# Clones sabnzb-cli into ~/.sabnzb-cli, installs it into a self-contained
# virtualenv, and links the `sab` command onto your PATH. Re-running updates
# an existing install in place.
#
# Options:
#   --uninstall   Remove the install and the `sab` / `sabnzb-cli` links.
#   --purge       Uninstall and also delete ~/.config/sabnzb-cli (your config).
#   -h, --help    Show this help.
#
# Environment overrides:
#   SABNZB_INSTALL_DIR   source/venv location   (default: ~/.sabnzb-cli)
#   SABNZB_BIN_DIR       where to link `sab`     (default: auto-detected)
#   SABNZB_REPO          git repo URL            (default: the GitHub repo)
#   SABNZB_REF           branch/tag to install   (default: master)

set -euo pipefail

REPO="${SABNZB_REPO:-https://github.com/elliott99ukhb/sabnzb-cli.git}"
REF="${SABNZB_REF:-master}"
INSTALL_DIR="${SABNZB_INSTALL_DIR:-$HOME/.sabnzb-cli}"
VENV="$INSTALL_DIR/.venv"
CONFIG_DIR="$HOME/.config/sabnzb-cli"

# ---- colours -----------------------------------------------------------------
if [ -t 1 ]; then
  BOLD=$'\033[1m'; DIM=$'\033[2m'; RED=$'\033[31m'; GREEN=$'\033[32m'
  YELLOW=$'\033[33m'; CYAN=$'\033[36m'; MAGENTA=$'\033[35m'; RESET=$'\033[0m'
else
  BOLD=""; DIM=""; RED=""; GREEN=""; YELLOW=""; CYAN=""; MAGENTA=""; RESET=""
fi
info()  { printf '%s==>%s %s\n' "$BOLD$MAGENTA" "$RESET" "$*"; }
ok()    { printf '  %s✓%s %s\n' "$GREEN" "$RESET" "$*"; }
warn()  { printf '%s!%s %s\n' "$YELLOW" "$RESET" "$*" >&2; }
abort() { printf '%serror:%s %s\n' "$RED" "$RESET" "$*" >&2; exit 1; }

banner() {
  printf '%s' "$BOLD$CYAN"
  cat <<'ART'
   ___      _
  / __| __ _| |__
  \__ \/ _` | '_ \
  |___/\__,_|_.__/
ART
  printf '%s  %ssabnzb-cli%s %s— command-line SABnzbd dashboard%s\n\n' \
    "$RESET" "$BOLD" "$RESET" "$DIM" "$RESET"
}

# Run a command as a labelled step: spinner on a TTY, tidy check/cross either
# way, and the captured log printed only if it fails.
run_step() {
  local msg=$1; shift
  local log; log=$(mktemp)
  if [ -t 1 ]; then
    ( "$@" ) >"$log" 2>&1 &
    local pid=$! frames='⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏' i=0
    while kill -0 "$pid" 2>/dev/null; do
      i=$(( (i + 1) % ${#frames} ))
      printf '\r  %s%s%s %s' "$CYAN" "${frames:$i:1}" "$RESET" "$msg"
      sleep 0.1
    done
    if wait "$pid"; then
      printf '\r  %s✓%s %s\033[K\n' "$GREEN" "$RESET" "$msg"
    else
      printf '\r  %s✗%s %s\033[K\n' "$RED" "$RESET" "$msg"
      cat "$log" >&2; rm -f "$log"; exit 1
    fi
  else
    if "$@" >"$log" 2>&1; then ok "$msg"; else
      printf '  %s✗%s %s\n' "$RED" "$RESET" "$msg"
      cat "$log" >&2; rm -f "$log"; exit 1
    fi
  fi
  rm -f "$log"
}

choose_bin_dir() {
  if [ -n "${SABNZB_BIN_DIR:-}" ]; then printf '%s' "$SABNZB_BIN_DIR"; return; fi
  for dir in "/opt/homebrew/bin" "/usr/local/bin" "$HOME/.local/bin"; do
    case ":$PATH:" in *":$dir:"*)
      if [ -d "$dir" ] && [ -w "$dir" ]; then printf '%s' "$dir"; return; fi ;;
    esac
  done
  printf '%s' "$HOME/.local/bin"
}

# ---- steps -------------------------------------------------------------------
do_fetch() {
  if [ -d "$INSTALL_DIR/.git" ]; then
    git -C "$INSTALL_DIR" fetch --quiet origin "$REF"
    git -C "$INSTALL_DIR" checkout --quiet "$REF"
    git -C "$INSTALL_DIR" reset --hard --quiet "origin/$REF" 2>/dev/null || git -C "$INSTALL_DIR" pull --quiet
  else
    git clone --quiet --branch "$REF" "$REPO" "$INSTALL_DIR"
  fi
}
do_venv()    { [ -x "$VENV/bin/python" ] || "$PYTHON" -m venv "$VENV"; }
do_install() {
  "$VENV/bin/python" -m pip install --quiet --upgrade pip
  "$VENV/bin/python" -m pip install --quiet -e "$INSTALL_DIR"
}
do_link() {
  for cmd in sab sabnzb-cli; do
    [ -x "$VENV/bin/$cmd" ] && ln -sf "$VENV/bin/$cmd" "$BIN_DIR/$cmd"
  done
}

# ---- install -----------------------------------------------------------------
install() {
  banner

  command -v git >/dev/null 2>&1 || abort "git is required but was not found. Install git and re-run."
  PYTHON=""
  for candidate in python3 python; do
    if command -v "$candidate" >/dev/null 2>&1; then PYTHON="$candidate"; break; fi
  done
  [ -n "$PYTHON" ] || abort "Python 3.9+ is required but no python3 was found."
  "$PYTHON" -c 'import sys; sys.exit(0 if sys.version_info[:2] >= (3, 9) else 1)' \
    || abort "Python 3.9+ is required (found $("$PYTHON" -V 2>&1))."
  info "Using $("$PYTHON" -V 2>&1)"

  BIN_DIR="$(choose_bin_dir)"
  mkdir -p "$BIN_DIR"

  if [ -d "$INSTALL_DIR/.git" ]; then
    info "Updating existing install in $INSTALL_DIR"
    run_step "Fetching latest source" do_fetch
  else
    [ -e "$INSTALL_DIR" ] && abort "$INSTALL_DIR exists but is not a git checkout. Remove it or set SABNZB_INSTALL_DIR."
    info "Installing to $INSTALL_DIR"
    run_step "Cloning repository" do_fetch
  fi
  run_step "Creating virtualenv" do_venv
  run_step "Installing sabnzb-cli and dependencies" do_install
  run_step "Linking sab onto your PATH" do_link

  echo
  printf '%s%s  sabnzb-cli is installed  %s\n' "$BOLD$GREEN" "★" "$RESET"

  case ":$PATH:" in
    *":$BIN_DIR:"*) : ;;
    *)
      echo
      warn "$BIN_DIR is not on your PATH."
      printf '  Add this to your shell profile (e.g. ~/.zshrc), then restart your shell:\n'
      printf '      %sexport PATH="%s:$PATH"%s\n' "$DIM" "$BIN_DIR" "$RESET"
      ;;
  esac

  echo
  printf '%sNext steps%s\n' "$BOLD" "$RESET"
  printf '  %s1%s  Configure SABnzbd:   %ssab --init%s   %s(then add your API key)%s\n' \
    "$CYAN" "$RESET" "$BOLD" "$RESET" "$DIM" "$RESET"
  printf '  %s2%s  Launch dashboard:    %ssab%s\n' "$CYAN" "$RESET" "$BOLD" "$RESET"
  echo
  printf '%sUpdate:%s re-run the installer.  %sUninstall:%s bash %s/install.sh --uninstall\n' \
    "$DIM" "$RESET" "$DIM" "$RESET" "$INSTALL_DIR"
}

# ---- uninstall ---------------------------------------------------------------
uninstall() {
  banner
  info "Uninstalling sabnzb-cli"

  # Remove any sab / sabnzb-cli symlinks that point into our install dir.
  local dirs=("$(choose_bin_dir)" "/opt/homebrew/bin" "/usr/local/bin" "$HOME/.local/bin")
  local found=0
  for d in "${dirs[@]}"; do
    for cmd in sab sabnzb-cli; do
      local link="$d/$cmd"
      if [ -L "$link" ]; then
        case "$(readlink "$link")" in
          "$INSTALL_DIR"/*) rm -f "$link"; ok "Removed link $link"; found=1 ;;
        esac
      fi
    done
  done
  [ "$found" -eq 0 ] && ok "No sabnzb-cli links found on PATH"

  if [ -d "$INSTALL_DIR" ]; then
    rm -rf "$INSTALL_DIR"; ok "Removed $INSTALL_DIR"
  else
    ok "No install found at $INSTALL_DIR"
  fi

  if [ "${PURGE:-0}" = "1" ]; then
    [ -d "$CONFIG_DIR" ] && { rm -rf "$CONFIG_DIR"; ok "Removed config $CONFIG_DIR"; }
  elif [ -f "$CONFIG_DIR/config.json" ]; then
    info "Kept your config at $CONFIG_DIR/config.json (use --purge to remove it too)"
  fi

  echo
  printf '%s%s  sabnzb-cli uninstalled  %s\n' "$BOLD$GREEN" "★" "$RESET"
}

# ---- arg parsing -------------------------------------------------------------
usage() { sed -n '2,30p' "$0" 2>/dev/null | sed 's/^#\{1,2\} \{0,1\}//; s/^#$//'; }

ACTION=install
PURGE=0
while [ $# -gt 0 ]; do
  case "$1" in
    --uninstall) ACTION=uninstall ;;
    --purge)     ACTION=uninstall; PURGE=1 ;;
    -h|--help)   usage; exit 0 ;;
    *)           abort "Unknown option: $1 (try --help)" ;;
  esac
  shift
done

"$ACTION"
