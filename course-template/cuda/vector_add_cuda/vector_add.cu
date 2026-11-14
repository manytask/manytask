// Reference solution. Public export replaces this file with the student stub.
#include "vector_add.hpp"

#include <cuda_runtime.h>

namespace {

__global__ void add_kernel(const float* a, const float* b, float* result,
                           std::size_t count) {
    const std::size_t index = static_cast<std::size_t>(blockIdx.x) * blockDim.x + threadIdx.x;
    if (index < count) {
        result[index] = a[index] + b[index];
    }
}

}  // namespace

void vector_add(const float* a, const float* b, float* result, std::size_t count) {
    if (count == 0) {
        return;
    }
    constexpr unsigned int threads = 256;
    const auto blocks = static_cast<unsigned int>((count + threads - 1) / threads);
    add_kernel<<<blocks, threads>>>(a, b, result, count);
}
