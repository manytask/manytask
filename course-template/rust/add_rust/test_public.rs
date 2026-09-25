// Visible tests. `include!` textually inlines the solution so a single rustc
// --test invocation builds one self-contained harness (no cargo). Resolved
// relative to this file, so it works from any cwd.
include!("add.rs");

#[test]
fn simple_positive() {
    assert_eq!(add(2, 3), 5);
}

#[test]
fn zero() {
    assert_eq!(add(0, 0), 0);
}

#[test]
fn mixed_signs() {
    assert_eq!(add(-1, 1), 0);
}
