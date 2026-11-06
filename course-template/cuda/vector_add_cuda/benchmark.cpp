#include "test_support.hpp"

#include <catch2/benchmark/catch_benchmark.hpp>

TEST_CASE("Vector addition throughput", "[benchmark]") {
    constexpr std::size_t count = 1 << 20;
    DeviceBuffer a(count), b(count), result(count);
    check_cuda(cudaMemset(a.data(), 0, count * sizeof(float)));
    check_cuda(cudaMemset(b.data(), 0, count * sizeof(float)));
    check_cuda(cudaDeviceSynchronize());

    BENCHMARK("vector_add") {
        vector_add(a.data(), b.data(), result.data(), count);
        check_cuda(cudaGetLastError());
        // Include completion of GPU work, rather than just kernel launch latency.
        check_cuda(cudaDeviceSynchronize());
    };
}
