# Optional CUDA group

`vector_add_cuda/` is a complete CUDA/Catch2 sample: a reference solution, a
`.cu.template` student stub, public tests, hidden tests and a benchmark.
`.group.yml` reuses the existing Catch2 plugins with generic `command_prefix` and
`env_whitelist` arguments. CUDA commands live in this course configuration.

The group is disabled in `.manytask.yml` by default. The standard template image
uses Alpine and has no CUDA toolchain. To enable this group:

1. Provide a Linux GPU worker with compatible NVIDIA drivers and the CUDA toolkit
   (including Compute Sanitizer), a C++ compiler supported by that toolkit,
   CMake 3.24+, Ninja, Firejail and an installed Catch2 v3 CMake package. Use a
   CUDA-compatible glibc-based image when running inside a container. Install a
   checker version containing the shared Catch2 execution options.
2. Make the GPU devices and driver libraries available to the worker/container and
   allow the required device access in Firejail. The worker assigns a GPU and sets
   `CUDA_VISIBLE_DEVICES` before starting the checker; the checker forwards it
   without treating it as a device isolation mechanism.
3. In `.manytask.yml`, set `enabled: true` on the `cuda` group. Adapt the
   `compute_sanitizer` executable path, environment allowlist and
   `benchmark_values` threshold in `cuda/.group.yml` to your worker. The default
   10 ms threshold is an example, not a portable GPU performance guarantee.
4. From the course root, run:

   ```bash
   checker validate .
   checker check . . --group cuda
   ```

The pipeline configures and builds the CMake targets, runs correctness tests,
repeats them through Compute Sanitizer, then benchmarks the ordinary binary.
The sanitizer stage has a separate timeout and sets `--error-exitcode 1`, so memory
errors fail grading. Benchmarks synchronize the device to include GPU execution.

When enabling this group in CI, both the private course check and student grading
jobs need the CUDA-capable image and GPU runner. Merely enabling the schedule
entry does not add CUDA to the template's ordinary image.

Public export replaces `vector_add.cu` with the student stub and omits
`test_private.cpp`. CMake conditionally includes the hidden tests, so students can
build the exported project using only the public files. Disabled groups are not
published at all. Local `build-*` directories are ignored during export.
