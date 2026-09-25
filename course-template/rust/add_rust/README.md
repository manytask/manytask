# add (Rust)

Implement a function that returns the sum of two integers.

## Signature

```rust
pub fn add(a: i64, b: i64) -> i64
```

Edit `add.rs` and implement `add`.

## Examples

```rust
add(2, 3)   // 5
add(-1, 1)  // 0
add(0, 0)   // 0
```

## How to run tests locally

```bash
rustc --edition 2021 --test test_public.rs -o /tmp/test_public && /tmp/test_public
```

The grader additionally compiles a hidden `test_private.rs` with edge cases.
