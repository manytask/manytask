#pragma once

#include "vector_add.hpp"

#include <catch2/catch_test_macros.hpp>
#include <cuda_runtime.h>

#include <cstddef>
#include <vector>

inline void check_cuda(cudaError_t error) {
    INFO(cudaGetErrorString(error));
    REQUIRE(error == cudaSuccess);
}

class DeviceBuffer {
public:
    explicit DeviceBuffer(std::size_t count) {
        if (count != 0) {
            check_cuda(cudaMalloc(reinterpret_cast<void**>(&data_), count * sizeof(float)));
        }
    }

    ~DeviceBuffer() {
        if (data_ != nullptr) {
            cudaFree(data_);
        }
    }

    DeviceBuffer(const DeviceBuffer&) = delete;
    DeviceBuffer& operator=(const DeviceBuffer&) = delete;

    float* data() const { return data_; }

private:
    float* data_ = nullptr;
};

inline void check_vector_add(std::size_t count) {
    std::vector<float> a(count), b(count), result(count);
    for (std::size_t i = 0; i < count; ++i) {
        a[i] = static_cast<float>(static_cast<int>(i % 97) - 48) / 4.0F;
        b[i] = static_cast<float>(static_cast<int>(i % 31) - 15) / 2.0F;
    }
    DeviceBuffer device_a(count), device_b(count), device_result(count);
    if (count != 0) {
        check_cuda(cudaMemcpy(device_a.data(), a.data(), count * sizeof(float), cudaMemcpyHostToDevice));
        check_cuda(cudaMemcpy(device_b.data(), b.data(), count * sizeof(float), cudaMemcpyHostToDevice));
    }

    vector_add(device_a.data(), device_b.data(), device_result.data(), count);
    check_cuda(cudaGetLastError());
    check_cuda(cudaDeviceSynchronize());
    if (count != 0) {
        check_cuda(cudaMemcpy(result.data(), device_result.data(), count * sizeof(float), cudaMemcpyDeviceToHost));
    }
    for (std::size_t i = 0; i < count; ++i) {
        CAPTURE(count, i);
        REQUIRE(result[i] == a[i] + b[i]);
    }
}
