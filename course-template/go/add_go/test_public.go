// Visible tests. Compiled with add.go via `go run`; exits non-zero on mismatch.
// Named test_public.go (not *_test.go) so it is an ordinary main, not a `go test`
// file — the grader drives it explicitly.
package main

import (
	"fmt"
	"os"
)

func check(got, want int, name string) int {
	if got != want {
		fmt.Fprintf(os.Stderr, "FAIL %s: got %d want %d\n", name, got, want)
		return 1
	}
	return 0
}

func main() {
	fails := 0
	fails += check(Add(2, 3), 5, "simple_positive")
	fails += check(Add(0, 0), 0, "zero")
	fails += check(Add(-1, 1), 0, "mixed_signs")
	if fails != 0 {
		os.Exit(1)
	}
}
