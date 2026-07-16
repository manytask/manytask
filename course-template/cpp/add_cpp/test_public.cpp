// Visible tests. Compiled together with add.cpp; a non-zero exit code fails the
// grading stage. Plain checks (not <cassert>) so the result is independent of
// NDEBUG / optimization flags.
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
    fails += check(add(2, 3), 5, "simple_positive");
    fails += check(add(0, 0), 0, "zero");
    fails += check(add(-1, 1), 0, "mixed_signs");
    return fails == 0 ? 0 : 1;
}
