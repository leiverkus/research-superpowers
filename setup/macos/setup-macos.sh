#!/usr/bin/env bash
# Set up a Mac for research-superpowers.
#
# Idempotent: run it again any time; it skips what is already there.
#
#   bash setup/macos/setup-macos.sh                    # from a clone of the repo
#   SKIP_OPTIONAL=1 bash setup/macos/setup-macos.sh    # without gh and the desktop app
#
# Without a clone:
#   curl -fsSL https://raw.githubusercontent.com/leiverkus/research-superpowers/main/setup/macos/setup-macos.sh | bash
#
# What Homebrew installs is listed in the Brewfile next to this script (fetched
# from GitHub when the script runs on its own). The script adds what Homebrew
# cannot do: PyYAML for Homebrew's Python, TeX via Quarto, the Claude login, the
# plugin itself, the dao-paper-search MCP server, and the pointer to your shared
# PDF library. See setup/macos/README.md for what each piece is for.

set -euo pipefail

RAW="https://raw.githubusercontent.com/leiverkus/research-superpowers/main/setup/macos"
DAO_MCP_VERSION="1.2.0"   # keep in step with docs/recommended-mcps.md (a test checks this)

say()  { printf '\n\033[1m==> %s\033[0m\n' "$*"; }
ok()   { printf '    ✓ %s\n' "$*"; }
warn() { printf '    ⚠ %s\n' "$*"; }
ask()  { local a; read -r -p "    $1 [y/N] " a </dev/tty; [[ "$a" =~ ^[yY]$ ]]; }

[[ "$(uname -s)" == "Darwin" ]] || { echo "This script is for macOS."; exit 1; }

# Brewfile: next to the script in a clone, otherwise fetched from GitHub. Piped
# through `curl | bash` the script has no directory of its own and "next to it"
# means the current one, so only a Brewfile carrying this project's header counts.
HERE="$(cd "$(dirname "${BASH_SOURCE[0]:-$0}")" 2>/dev/null && pwd || echo "")"
if [[ -n "$HERE" && -f "$HERE/Brewfile" ]] \
   && head -1 "$HERE/Brewfile" | grep -q '^# Brewfile for research-superpowers'; then
  BREWFILE="$HERE/Brewfile"
else
  BREWFILE="${TMPDIR:-/tmp}/research-superpowers.Brewfile"
  curl -fsSL "$RAW/Brewfile" -o "$BREWFILE"
fi

# --- 1. Xcode Command Line Tools (git, make, compilers) -------------------
say "Xcode Command Line Tools"
if xcode-select -p >/dev/null 2>&1; then
  ok "present"
else
  xcode-select --install || true
  warn "Installation started. Finish the dialog, then run this script again."
  exit 0
fi

# --- 2. Homebrew -----------------------------------------------------------
say "Homebrew"
if ! command -v brew >/dev/null 2>&1; then
  for b in /opt/homebrew/bin/brew /usr/local/bin/brew; do
    [[ -x "$b" ]] && eval "$("$b" shellenv)" && break
  done
fi
if command -v brew >/dev/null 2>&1; then
  ok "$(brew --version | head -1)"
else
  echo "    Homebrew is missing. Official installer (https://brew.sh):"
  echo '    /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"'
  if ask "Install it now?"; then
    /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
    eval "$(/opt/homebrew/bin/brew shellenv 2>/dev/null || /usr/local/bin/brew shellenv)"
  else
    exit 1
  fi
fi

# --- 3. Packages from the Brewfile -----------------------------------------
say "Packages (Brewfile)"
if [[ "${SKIP_OPTIONAL:-}" == "1" ]]; then
  grep -vE '^(brew "gh"|cask "claude")([[:space:]]|$)' "$BREWFILE" > "${TMPDIR:-/tmp}/research-superpowers.core.Brewfile"
  BREWFILE="${TMPDIR:-/tmp}/research-superpowers.core.Brewfile"
fi
brew bundle --file "$BREWFILE"
ok "Brewfile installed"

# Homebrew's Python must come first on PATH, not macOS's /usr/bin/python3 (3.9).
BREW_PY="$(brew --prefix)/bin/python3"
PY_VER="$("$BREW_PY" -c 'import sys; print("%d.%d" % sys.version_info[:2])')"
if [[ "$(command -v python3)" != "$BREW_PY" ]]; then
  warn "python3 on PATH is $(command -v python3), not Homebrew's $BREW_PY."
  warn "Add to ~/.zprofile: eval \"\$($(brew --prefix)/bin/brew shellenv)\""
fi
ok "Python $PY_VER ($BREW_PY)"

# --- 4. PyYAML (the one library the wiki scripts need) ---------------------
say "PyYAML"
if "$BREW_PY" -c 'import yaml' 2>/dev/null; then
  ok "present"
else
  # Homebrew's Python is "externally managed" (PEP 668); a --user install only
  # touches ~/Library/Python and leaves Homebrew's packages alone.
  "$BREW_PY" -m pip install --user --break-system-packages --quiet pyyaml
  "$BREW_PY" -c 'import yaml' && ok "installed"
fi

# --- 5. TeX for PDF output (Quarto's TinyTeX) -------------------------------
say "TeX (TinyTeX via Quarto)"
# `quarto list tools` reports tinytex as "Up to date", "Update available" or
# "Not installed"; only the last one needs an install.
if quarto list tools 2>/dev/null | grep -E '^[^a-z]*tinytex' | grep -vq 'Not installed' \
   || command -v xelatex >/dev/null 2>&1; then
  ok "present"
else
  quarto install tinytex --no-prompt
  ok "installed (Quarto fetches missing LaTeX packages on the first PDF render)"
fi

# --- 6. Claude Code login -----------------------------------------------------
say "Claude Code"
ok "$(claude --version)"
if claude auth status 2>/dev/null | grep -q '"loggedIn": true'; then
  ok "signed in"
else
  warn "Not signed in. A browser window opens."
  claude auth login
fi
if [[ -x "$HOME/.local/bin/claude" && "$(command -v claude)" != "$HOME/.local/bin/claude" ]]; then
  warn "A second Claude Code install sits in ~/.local/bin (native installer). Keep one,"
  warn "or two versions run side by side."
fi

# --- 7. The plugin ------------------------------------------------------------
say "research-superpowers"
if claude plugin marketplace list 2>/dev/null | grep -q 'leiverkus-research'; then
  claude plugin marketplace update leiverkus-research >/dev/null
  ok "marketplace updated"
else
  claude plugin marketplace add leiverkus/research-superpowers
fi
if claude plugin list 2>/dev/null | grep -q 'research-superpowers@leiverkus-research'; then
  claude plugin update research-superpowers@leiverkus-research
else
  claude plugin install research-superpowers@leiverkus-research --scope user
fi
ok "installed — takes effect in the next Claude session"

# --- 8. dao-paper-search MCP (recommended) -------------------------------------
say "dao-paper-search MCP (recommended)"
if claude mcp get dao-paper-search >/dev/null 2>&1; then
  ok "already configured: $(claude mcp get dao-paper-search | grep -E 'Args' | sed 's/^ *//')"
  warn "Check the version: recommended is dao-paper-search-mcp==$DAO_MCP_VERSION"
elif ask "Set it up? (DAO catalogues, verified citation lines, authority IDs)"; then
  read -r -p "    Contact e-mail for the APIs' polite pool (Enter = none): " MAIL </dev/tty
  read -r -s -p "    CORE_API_KEY (for search_core; Enter = skip): " CORE </dev/tty; echo
  ENVARGS=(-e "DAO_PAPER_SEARCH_RATE_LIMIT_MS=1000")
  [[ -n "${MAIL:-}" ]] && ENVARGS+=(-e "DAO_PAPER_SEARCH_CONTACT_EMAIL=$MAIL")
  [[ -n "${CORE:-}" ]] && ENVARGS+=(-e "CORE_API_KEY=$CORE")
  claude mcp add dao-paper-search -s user "${ENVARGS[@]}" -- \
    uvx --from "dao-paper-search-mcp==$DAO_MCP_VERSION" dao-paper-search-mcp
  unset CORE
  ok "configured"
fi

# --- 9. Shared PDF library ------------------------------------------------------
say "Shared PDF library"
CONF="$HOME/.config/research-superpowers/library"
if [[ -s "$CONF" ]]; then
  ok "path set: $(cat "$CONF")"
else
  echo "    All projects share one library (<library>/references.bib, <library>/pdf/<bibkey>.pdf)."
  read -r -p "    Path (e.g. ~/Nextcloud/Library; Enter = later): " LIB </dev/tty
  if [[ -n "${LIB:-}" ]]; then
    LIB="${LIB/#\~/$HOME}"
    mkdir -p "$LIB/pdf" "$(dirname "$CONF")"
    printf '%s\n' "$LIB" > "$CONF"
    ok "set: $LIB"
  else
    warn "Later: write the path as one line into $CONF"
  fi
fi

# --- 10. Check ------------------------------------------------------------------
say "Check"
check() { if eval "$2" >/dev/null 2>&1; then ok "$1"; else warn "$1 — missing"; FAIL=1; fi; }
FAIL=0
check "git"                              "git --version"
check "Python >= 3.10 with PyYAML"       "\"$BREW_PY\" -c 'import sys, yaml; assert sys.version_info >= (3, 10)'"
check "uvx"                              "uvx --version"
check "pdftotext / pdfinfo"              "pdftotext -v && pdfinfo -v"
check "ghostscript"                      "gs --version"
check "ocrmypdf (German, Hebrew)"        "tesseract --list-langs 2>&1 | grep -qx deu && tesseract --list-langs 2>&1 | grep -qx heb && ocrmypdf --version"
check "quarto"                           "quarto --version"
check "fonts (Gentium Plus, Noto Sans, Fira Code, Ezra SIL)" \
      "brew list --cask font-gentium-plus font-noto-sans font-fira-code font-ezra-sil"
check "Zettlr"                           "brew list --cask zettlr"
check "Claude Code signed in"            "claude auth status | grep -q '\"loggedIn\": true'"
check "plugin installed"                 "claude plugin list | grep -q research-superpowers"

echo
if [[ "$FAIL" == "0" ]]; then
  echo "Done. New project: tell Claude Code \"set up a new research project\" (scaffold-research-project)."
else
  echo "Done, with warnings (above). The script is safe to run again."
fi
