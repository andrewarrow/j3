# TRANS-003 GreenShot-5 Manifest Expansion

Task: `TRANS-003`

## Decision

Expand only the standard matrix manifest's `greenshot_5_subset` selection from
8 to 12 tasks. This is a manifest-only expansion from the zero-matrix-residual
`TRANS-011` baseline.

The added tasks are:

- `profile_badge_public_api_signature_propagation`
- `return_window_policy_default`
- `receipt_label_nested_module_import_decoy`
- `loyalty_points_wrapper_exception_handler`

The resulting GreenShot-5 subset follows the order in
`examples/greenshot_5/tasks.json` and remains a subset of the 20-task
GreenShot-5 manifest.

## Non-Changes

- No scorer, ranker, candidate-generation, product-routing, or guarded-trial
  policy code changed.
- Transition ranking product routing remains shadow-only.
- The standard matrix suites and runner parameters are unchanged.

## Follow-Up

Run the expanded standard transition shadow matrix as a separate evidence step.
That follow-up should record matrix totals, residuals, suite gates, guarded
decision, and whether the expansion preserves the zero-matrix-residual
`TRANS-011` baseline.
