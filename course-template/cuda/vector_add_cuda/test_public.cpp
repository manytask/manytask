#include "test_support.hpp"

TEST_CASE("Vector addition: public examples", "[public]") {
    for (const std::size_t count : {0, 1, 4, 256}) {
        DYNAMIC_SECTION("count = " << count) {
            check_vector_add(count);
        }
    }
}
