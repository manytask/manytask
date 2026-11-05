// Hidden grading tests. Excluded from public export by the *private* rule.
#include "test_support.hpp"

TEST_CASE("Vector addition: block boundaries and larger inputs", "[private]") {
    for (const std::size_t count : {255, 257, 1023, 4097, 65537}) {
        DYNAMIC_SECTION("count = " << count) {
            check_vector_add(count);
        }
    }
}
