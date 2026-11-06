#pragma once

#include <cstddef>

// All pointers refer to device memory containing count floats.
// Launch work on the default stream; the caller synchronizes and checks errors.
// For count == 0, do not launch a kernel or access any pointer.
void vector_add(const float* a, const float* b, float* result, std::size_t count);
