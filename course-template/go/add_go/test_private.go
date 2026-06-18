// Hidden grading tests (NOT exported — kept private by the "*private*" rule in
// .checker.yml). Edge cases.
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
	fails += check(Add(1000000, 2000000), 3000000, "large")
	fails += check(Add(-7, -8), -15, "both_negative")
	if Add(123, 456) != Add(456, 123) {
		fmt.Fprintln(os.Stderr, "FAIL commutative")
		fails++
	}
	if fails != 0 {
		os.Exit(1)
	}
}
