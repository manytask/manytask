#!/usr/bin/env bash
# Deploy course-template/ (the monorepo source of truth) to the GitLab
# private repo. Usage: course-template/deploy.sh git@gitlab.manytask2.org:sandbox/private.git
set -euo pipefail

REMOTE="${1:?usage: deploy.sh <gitlab-private-remote-url>}"
SRC="$(cd "$(dirname "$0")" && pwd)"
WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT

git clone "$REMOTE" "$WORK" 2>/dev/null || { git init "$WORK"; git -C "$WORK" remote add origin "$REMOTE"; }
# Mirror source over the clone (delete removed files; never touch .git or the script itself)
rsync -a --delete --exclude '.git' --exclude 'deploy.sh' "$SRC"/ "$WORK"/
git -C "$WORK" add -A
git -C "$WORK" commit -m "chore: sync course template from monorepo" || { echo "nothing to deploy"; exit 0; }
git -C "$WORK" push origin HEAD:main
echo "deployed to $REMOTE"
