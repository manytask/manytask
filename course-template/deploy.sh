#!/usr/bin/env bash
# Deploy course-template/ (the monorepo source of truth) to the GitLab
# private repo. Usage: course-template/deploy.sh git@gitlab.manytask2.org:sandbox/private.git
set -euo pipefail

REMOTE="${1:?usage: deploy.sh <gitlab-private-remote-url>}"
SRC="$(cd "$(dirname "$0")" && pwd)"
WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT

# Clone the remote; if that fails (new/empty repo, or a real error — git prints
# why to stderr), fall back to initialising a fresh repo pointed at the remote.
git clone "$REMOTE" "$WORK" || {
  echo "git clone failed (new/empty remote? check the error above); initialising fresh" >&2
  git init "$WORK"
  git -C "$WORK" remote add origin "$REMOTE"
}
# Mirror source over the clone (delete removed files; never touch .git or the script itself)
rsync -a --delete --exclude '.git' --exclude 'deploy.sh' "$SRC"/ "$WORK"/
git -C "$WORK" add -A
# Force a commit identity so an unconfigured global git identity can't make an
# "empty ident" failure look like a clean "nothing to deploy".
git -C "$WORK" -c user.name="manytask-ci" -c user.email="ci@manytask.org" \
  commit -m "chore: sync course template from monorepo" || { echo "nothing to deploy"; exit 0; }
git -C "$WORK" push origin HEAD:main
echo "deployed to $REMOTE"
