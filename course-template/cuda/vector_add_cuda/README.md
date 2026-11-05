# Vector addition (CUDA)

Implement `vector_add` in `vector_add.cu` using a CUDA kernel. The three pointers
refer to device arrays of `count` floats. Compute `result[i] = a[i] + b[i]` for every
valid index, including when `count` is not divisible by the block size. For an empty
array, return without launching a kernel or touching the pointers.

Launch on the default stream. The test driver synchronizes the device and checks
CUDA errors after each call. Only edit `vector_add.cu`; keep the header and test
drivers unchanged.

## Local tests

You need a CUDA-capable GPU, the CUDA toolkit, CMake 3.24+, Ninja and an installed
Catch2 v3 CMake package. See [the CUDA group guide](../README.md) for checker setup.

```bash
cmake -S . -B build-relwithdebinfo -G Ninja -DCMAKE_BUILD_TYPE=RelWithDebInfo
cmake --build build-relwithdebinfo
ctest --test-dir build-relwithdebinfo --output-on-failure
/usr/local/cuda/bin/compute-sanitizer --tool memcheck --leak-check full \
  --error-exitcode 1 ./build-relwithdebinfo/cuda_tests
./build-relwithdebinfo/cuda_benchmarks
```

Set `CMAKE_CUDA_ARCHITECTURES` when configuring if your course requires a particular
GPU architecture, and `Catch2_DIR` if Catch2 is installed outside CMake's search
paths. The grader adds hidden test cases. Benchmarks synchronize GPU work and run
without sanitizer instrumentation; their time limits depend on the worker's GPU.
