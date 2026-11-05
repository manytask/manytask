cmake_minimum_required(VERSION 3.24)
project(vector_add_cuda LANGUAGES CXX CUDA)

find_package(CUDAToolkit REQUIRED)
find_package(Catch2 3 REQUIRED)

add_library(vector_add STATIC vector_add.cu)
target_compile_features(vector_add PUBLIC cxx_std_17 cuda_std_17)
target_link_libraries(vector_add PUBLIC CUDA::cudart)

add_executable(cuda_tests test_public.cpp)
# The exported student project must build without the hidden grading tests.
if(EXISTS "${CMAKE_CURRENT_SOURCE_DIR}/test_private.cpp")
    target_sources(cuda_tests PRIVATE test_private.cpp)
endif()
target_link_libraries(cuda_tests PRIVATE vector_add Catch2::Catch2WithMain)

add_executable(cuda_benchmarks benchmark.cpp)
target_link_libraries(cuda_benchmarks PRIVATE vector_add Catch2::Catch2WithMain)

enable_testing()
add_test(NAME cuda_tests COMMAND cuda_tests)
