#!/usr/bin/env bash
#
# git-push.sh - Commit & push the project to GitHub safely.
#
# Brush of one command for Back4app/Vercel (both auto-deploy from GitHub).
# Verbatim it: stage -> (*) -> commit -> push, and it REFUSES to stage secrets.
#
# Usage:
#   ./git-push.sh                              # default commit message
#   ./git-push.sh "fix: my message"            # custom message
#   PUSH_YES=1 ./git-push.sh                   # skip the confirmation prompt
#   GIT_REMOTE=https://github.com/USER/REPO.git ./git-push.sh  # first run
#
# Prereqs: Git Bash / WSL with the git CLI. Works whether the folder already
# has a repo or not (it initializes + sets origin on first run).

set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")"

COMMIT_MSG="${1:-fix(client,backend): align API base URL resolution and make the backend PORT-aware for Back4app}"
BOLD=$'\033[1m'; RED=$'\033[31m'; DIM=$'\033[2m'; NC=$'\033[0m'

# --------------------------------------------------------------------------- #
# 1) .gitignore - make sure secrets & build junk can never be staged.          #
# --------------------------------------------------------------------------- #
NEEDED_PATTERNS=("**/.env" "node_modules/" ".next/" "data/" "__pycache__/" "*.log")
if [ ! -f .gitignore ]; then
  cat > .gitignore <<'EOF'
# Secrets - never commit
.env
**/.env
.env.*
!.env.example

# Python / backend
__pycache__/
*.py[cod]
venv/
.venv/

# Runtime data & artifacts
data/
*.log

# Frontend / Node
node_modules/
.next/
out/

# OS
.DS_Store
Thumbs.db
EOF
  echo "${BOLD}[git-push]${NC} Created a fresh .gitignore (secrets excluded)."
else
  for p in "${NEEDED_PATTERNS[@]}"; do
    grep -qxF "$p" .gitignore || printf '\n%s\n' "$p" >> .gitignore
  done
  echo "${BOLD}[git-push]${NC} .gitignore present; ensured critical patterns exist."
fi

# --------------------------------------------------------------------------- #
# 2) Hard safety - abort if a secret is already tracked.                       #
# --------------------------------------------------------------------------- #
for f in backend/.env .env backend/.env.local; do
  if [ -f "$f" ] && git ls-files --error-unmatch "$f" >/dev/null 2>&1; then
    echo "${RED}ABORT:${NC} $f is TRACKED. De-list it once, then re-run:" >&2
    echo "  git rm --cached '$f'" >&2
    exit 1
  fi
done

# --------------------------------------------------------------------------- #
# 3) Ensure it's a git repo on a sensible branch.                              #
# --------------------------------------------------------------------------- #
if ! git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  git init -b main 2>/dev/null || { git init; git checkout -b main; }
  echo "${BOLD}[git-push]${NC} Initialized a new repo on branch 'main'."
fi
[ -n "$(git branch --show-current)" ] || git checkout -b main

# Remote (prompt once if missing).
if [ -z "$(git remote get-url origin 2>/dev/null)" ]; then
  if [ -n "${GIT_REMOTE:-}" ]; then
    git remote add origin "$GIT_REMOTE"
  else
    read -r -p "GitHub repo URL (HTTPS, e.g. https://github.com/USER/REPO.git): " url
    [ -n "$url" ] || { echo "No remote configured - run: git remote add origin <url>"; exit 1; }
    git remote add origin "$url"
  fi
fi

# Identity (first commit needs it).
git config user.name  >/dev/null 2>&1 || git config user.name  "${GIT_AUTHOR_NAME:-Developer}"
git config user.email >/dev/null 2>&1 || git config user.email "${GIT_AUTHOR_EMAIL:-dev@example.com}"

# --------------------------------------------------------------------------- #
# 4) Stage, then do one more secret sweep on WHAT WILL BE COMMITTED.           #
# --------------------------------------------------------------------------- #
git add -A

STAGED_SECRET=$(git diff --cached --name-only | grep -E '(^|/)(\.env|\.env\.local)$' || true)
if [ -n "$STAGED_SECRET" ]; then
  echo "${RED}ABORT:${NC} secret file staged: $STAGED_SECRET" >&2
  exit 1
fi

echo
echo "${BOLD}===== About to commit ($(git diff --cached --name-only | wc -l | tr -d ' ') files) =====${NC}"
git status --short
echo "${BOLD}================================================================${NC}"

if [ "${PUSH_YES:-0}" != "1" ]; then
  read -r -p "Commit & push these files? [y/N] " ans
  case "$ans" in y|Y) ;; *) echo "Aborted by user."; exit 1 ;; esac
fi

# --------------------------------------------------------------------------- #
# 5) Commit + push.                                                            #
# --------------------------------------------------------------------------- #
git commit -m "$COMMIT_MSG"

if git rev-parse --abbrev-ref --symbolic-full-name @{u} >/dev/null 2>&1; then
  git push
else
  git push -u origin "$(git branch --show-current)"
fi

echo
echo "${BOLD}DONE ✓ pushed to origin/$(git branch --show-current).${NC}"
echo "Back4app & Vercel will auto-deploy from this push."