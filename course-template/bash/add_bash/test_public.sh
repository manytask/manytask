#!/usr/bin/env bash
# Visible tests. Sources add.sh and checks `add`; exits non-zero on any mismatch.
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

check "$(add 2 3)" 5 simple_positive
check "$(add 0 0)" 0 zero
check "$(add -1 1)" 0 mixed_signs

[[ "$fails" -eq 0 ]]
