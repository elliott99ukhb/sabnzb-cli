#!/bin/bash
#
# sabnzb-cli installer
#
#   /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/elliott99ukhb/sabnzb-cli/master/install.sh)"
#
# Clones sabnzb-cli into ~/.sabnzb-cli, installs it into a self-contained
# virtualenv, and links the `sab` command onto your PATH. Re-running the
# script updates an existing install in place.
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

# ---- pretty output -----------------------------------------------------------
if [ -t 1 ]; then
  BOLD="$(printf '\033[1m')"; DIM="$(printf '\033[2m')"; RED="$(printf '\033[31m')"
  GREEN="$(printf '\033[32m')"; YELLOW="$(printf '\033[33m')"; RESET="$(printf '\033[0m')"
else
  BOLD=""; DIM=""; RED=""; GREEN=""; YELLOW=""; RESET=""
fi
info()  { printf '%s==>%s %s\n' "$BOLD" "$RESET" "$*"; }
ok()    { printf '%s✓%s %s\n' "$GREEN" "$RESET" "$*"; }
warn()  { printf '%s!%s %s\n' "$YELLOW" "$RESET" "$*" >&2; }
abort() { printf '%serror:%s %s\n' "$RED" "$RESET" "$*" >&2; exit 1; }

# ---- prerequisites -----------------------------------------------------------
command -v git >/dev/null 2>&1 || abort "git is required but was not found. Install git and re-run."

PYTHON=""
for candidate in python3 python; do
  if command -v "$candidate" >/dev/null 2>&1; then PYTHON="$candidate"; break; fi
done
[ -n "$PYTHON" ] || abort "Python 3.9+ is required but no python3 was found."

# Require Python >= 3.9
if ! "$PYTHON" -c 'import sys; sys.exit(0 if sys.version_info[:2] >= (3, 9) else 1)'; then
  abort "Python 3.9+ is required (found $("$PYTHON" -V 2>&1))."
fi
ok "Using $("$PYTHON" -V 2>&1) at $(command -v "$PYTHON")"

# ---- pick a bin dir on PATH --------------------------------------------------
choose_bin_dir() {
  if [ -n "${SABNZB_BIN_DIR:-}" ]; then printf '%s' "$SABNZB_BIN_DIR"; return; fi
  # Prefer an existing, writable directory that is already on PATH.
  for dir in "/opt/homebrew/bin" "/usr/local/bin" "$HOME/.local/bin"; do
    case ":$PATH:" in *":$dir:"*)
      if [ -d "$dir" ] && [ -w "$dir" ]; then printf '%s' "$dir"; return; fi ;;
    esac
  done
  # Fall back to ~/.local/bin (created if needed).
  printf '%s' "$HOME/.local/bin"
}
BIN_DIR="$(choose_bin_dir)"
mkdir -p "$BIN_DIR"

# ---- fetch / update source ---------------------------------------------------
if [ -d "$INSTALL_DIR/.git" ]; then
  info "Updating existing install in $INSTALL_DIR"
  git -C "$INSTALL_DIR" fetch --quiet origin "$REF"
  git -C "$INSTALL_DIR" checkout --quiet "$REF"
  git -C "$INSTALL_DIR" reset --hard --quiet "origin/$REF" 2>/dev/null || git -C "$INSTALL_DIR" pull --quiet
else
  [ -e "$INSTALL_DIR" ] && abort "$INSTALL_DIR exists but is not a git checkout. Remove it or set SABNZB_INSTALL_DIR."
  info "Cloning $REPO into $INSTALL_DIR"
  git clone --quiet --branch "$REF" "$REPO" "$INSTALL_DIR"
fi
ok "Source ready at $INSTALL_DIR"

# ---- build the virtualenv ----------------------------------------------------
VENV="$INSTALL_DIR/.venv"
if [ ! -x "$VENV/bin/python" ]; then
  info "Creating virtualenv"
  "$PYTHON" -m venv "$VENV"
fi
info "Installing sabnzb-cli and dependencies"
"$VENV/bin/python" -m pip install --quiet --upgrade pip
"$VENV/bin/python" -m pip install --quiet -e "$INSTALL_DIR"
ok "Installed into $VENV"

# ---- link commands onto PATH -------------------------------------------------
for cmd in sab sabnzb-cli; do
  target="$VENV/bin/$cmd"
  [ -x "$target" ] || continue
  ln -sf "$target" "$BIN_DIR/$cmd"
done
ok "Linked ${BOLD}sab${RESET} → $BIN_DIR/sab"

# ---- final guidance ----------------------------------------------------------
echo
ok "sabnzb-cli is installed."

case ":$PATH:" in
  *":$BIN_DIR:"*) : ;;
  *)
    warn "$BIN_DIR is not on your PATH."
    printf '  Add this line to your shell profile (e.g. ~/.zshrc):\n'
    printf '      %sexport PATH="%s:$PATH"%s\n' "$DIM" "$BIN_DIR" "$RESET"
    ;;
esac

echo
printf 'Next steps:\n'
printf '  1. Configure your SABnzbd connection:  %ssab --init%s\n' "$BOLD" "$RESET"
printf '     (writes a template to ~/.config/sabnzb-cli/config.json — add your API key)\n'
printf '  2. Launch the dashboard:               %ssab%s\n' "$BOLD" "$RESET"
echo
printf '%sUpdate later by re-running this installer. Uninstall with:%s\n' "$DIM" "$RESET"
printf '  rm -rf "%s" "%s/sab" "%s/sabnzb-cli"\n' "$INSTALL_DIR" "$BIN_DIR" "$BIN_DIR"
