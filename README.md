# j3

JEPA is naturally a predictor/planner, not a text generator. So we should not ask it to free-form generate arbitrary source text like an LLM.

  we define a structured patch action space:

  replace_expr
  insert_guard
  change_literal
  change_operator
  swap_call_arg
  add_import
  change_attribute
  wrap_try_except
  change_return_value
  rename_symbol
  modify_condition

  Then Code-JEPA chooses the edit action, target AST node, and parameters from the repo symbol table. A deterministic
  patch engine turns that action into a real diff.

  So the model makes the patch, but through structured edits rather than next-token generation.

  First Demo: GreenShot-1
  Input:

  A Python repo with one failing pytest failure.

  Output:

  One patch attempt, generated without an LLM.

  Flow:

  repo + failing test log
        ↓
  encode repo state into latent space
        ↓
  predict which edit moves state toward "tests pass"
        ↓
  materialize structured edit as patch
        ↓
  run tests once

  Command shape:

  codemesh patch --repo ~/my_project --test "pytest tests/test_parser.py::test_edge_case"

  Expected output:

  - if value > limit:
  + if value >= limit:

  or:

  + from pathlib import Path

  or:

  - return items[0]
  + return items[-1]

  What Runs Locally
  On your Mac Studio, I would build this with:

  - libcst or tree-sitter for Python ASTs
  - pytest log parser
  - lightweight graph/transformer encoder
  - MLX or PyTorch MPS backend
  - local SQLite/DuckDB transition cache
  - no hosted LLM dependency

  Apple’s MLX is designed for Apple silicon unified memory, and PyTorch’s MPS backend supports GPU acceleration on Apple
  hardware:

  - https://opensource.apple.com/projects/mlx/
  - https://docs.pytorch.org/docs/stable/notes/mps

  Training Data
  Start with data we can generate locally:

  1. Take passing Python repos.
  2. Mutate them into failing versions.
  3. Store:

  before_state + failing_log + repair_action -> after_state

  4. Train Code-JEPA to predict the latent after-state and learn which action reduces failure.

  Then add SWE-smith because it already generates many software-engineering tasks from Python repos:

  - https://swesmith.com/
  - https://arxiv.org/abs/2504.21798

  Why This Uses Fewer Tokens
  In pure mode, there are no LLM tokens.

  Internally, the model still reads code, but it does not repeatedly stuff whole files, logs, and instructions into an
  autoregressive context. It caches file/AST embeddings and predicts over compact latent states.

  The bottleneck becomes:

  parsing + model inference + pytest runtime

  not prompt size.

  Realistic First Target
  Do not start with arbitrary SWE-bench. Start with a controlled benchmark:

  - wrong operator
  - wrong literal
  - missing import
  - wrong function argument
  - missing guard
  - bad return expression
  - simple exception handling
  - off-by-one indexing
  - incorrect attribute access

  First success metric:

  pass@1: one JEPA-generated patch, one test run

  A strong first result would be:

  30-50% pass@1 on held-out synthetic repo bugs
  10-25% pass@1 on a constrained SWE-smith subset

  That would already be interesting because it proves a non-LLM latent world model can produce useful first patches
  locally.

  Revised Project Claim
  The MVP should say:

  > CodeMesh-JEPA is a local-first JEPA coding agent that repairs Python repos by planning structured edits in latent
  > repo space, using no LLM-generated patch candidates.

  That is a sharper and more original first demo.
