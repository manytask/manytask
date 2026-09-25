// Hidden grading tests (NOT exported — kept private by the "*private*" rule in
// .checker.yml). Edge cases stay within int range.
#include <iostream>

int add(int a, int b);

static int check(int got, int want, const char* name) {
    if (got != want) {
        std::cerr << "FAIL " << name << ": got " << got << " want " << want << "\n";
        return 1;
    }
    return 0;
}

int main() {
    int fails = 0;
    fails += check(add(1000000, 2000000), 3000000, "large");
    fails += check(add(-7, -8), -15, "both_negative");
    if (add(123, 456) != add(456, 123)) {
        std::cerr << "FAIL commutative\n";
        fails += 1;
    }
    return fails == 0 ? 0 : 1;
}
