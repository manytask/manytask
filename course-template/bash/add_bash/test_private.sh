#!/usr/bin/env bash
# Hidden grading tests (NOT exported — kept private by the "*private*" rule in
# .checker.yml). Edge cases.
set -uo pipefail

# shellcheck source=/dev/null
source "$(dirname "$0")/add.sh"

fails=0
check() {
    local got="$1" want="$2" name="$3"
    if [[ "$got" != "$want" ]]; then
        echo "FAIL $name: got $got want $want" >&2
        fails=$((fails + 1))
    fi
}

check "$(add 1000000 2000000)" 3000000 large
check "$(add -7 -8)" -15 both_negative
check "$(add 123 456)" "$(add 456 123)" commutative

[[ "$fails" -eq 0 ]]
