# add (C++)

Implement a function that returns the sum of two integers.

## Signature

```cpp
int add(int a, int b);
```

Edit `add.cpp` and implement `add`.

## Examples

```cpp
add(2, 3)   // 5
add(-1, 1)  // 0
add(0, 0)   // 0
```

## How to run tests locally

```bash
g++ -std=c++17 -Wall add.cpp test_public.cpp -o /tmp/test_public && /tmp/test_public
```

The grader additionally compiles a hidden `test_private.cpp` with edge cases.
