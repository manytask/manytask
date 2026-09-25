// Hidden grading tests (NOT exported — kept private by the "*private*" rule in
// .checker.yml). Edge cases.
include!("add.rs");

#[test]
fn large() {
    assert_eq!(add(1_000_000_000_000, 1_000_000_000_000), 2_000_000_000_000);
}

#[test]
fn both_negative() {
    assert_eq!(add(-7, -8), -15);
}

#[test]
fn commutative() {
    assert_eq!(add(123, 456), add(456, 123));
}
