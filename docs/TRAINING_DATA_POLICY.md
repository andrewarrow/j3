# Training Data Provenance And Release Policy

Date: 2026-05-19

This policy defines how `j3` may collect, retain, split, train on, and release
larger local training corpora. It builds on
`docs/SCALE_001_LOCAL_PRETRAINING_FEASIBILITY_INVENTORY_2026-05-19.md`: near
term learning is allowed for local encoders, rankers, retrieval, and
shadow-only transition models, while broad language/code pretraining remains
blocked until data volume, objective, compute, evaluation, and release controls
are explicit.

The default rule is conservative: raw third-party source, docs, issue text, PR
text, comments, generated candidates derived from third-party repos, and live
validation logs remain local-only unless a reviewed manifest record says
otherwise.

## Artifact Classes

| Class | Examples | Retention | Redistribution |
| --- | --- | --- | --- |
| Local scratch corpora | `/tmp/j3-*`, ignored `data/`, ignored `runs/`, local repo clones such as `/Users/aa/os/python-apache` | Keep only while the experiment is active. Promote only by creating a durable manifest row with checksums and review status. | Local-only. Do not include raw payloads in git or model release archives. |
| Checked-in examples | Small fixtures under `examples/`, test fixtures, compact manifest JSON/JSONL | Retain in git when reviewed, small, and useful for regression tests. | Redistributable only when project-owned, synthetic, or license/terms-reviewed and not a substantial third-party payload. |
| Release archives | Model checkpoints, metrics, manifests, eval reports, model cards | Retain under versioned release directories or tags. | May include manifests, hashes, metrics, and small owned examples. Must exclude raw external repo snapshots, issue/PR bodies, raw docs, and derived candidate source unless explicitly cleared. |
| Synthetic rows | Prompt templates, generated prompt/spec rows, synthetic transitions, mutation rows | Retain when generator, seed, template family, and split are recorded. | Redistributable if generated from project-owned templates and not copied from local-only raw records or teacher private output. |
| Issue/PR mining | Issue bodies, PR bodies, comments, accepted diffs, patch URLs, validation recipes | Raw harvested text stays local scratch until reviewed. Durable rows should store compact metadata and checksums first. | Raw issue/PR text and raw patches are local-only by default. Release only IDs, URLs, refs, checksums, labels, and short reviewed summaries unless terms and license review approves more. |
| Generated artifacts | Candidate diffs, candidate-after snapshots, validation logs, residual reports, hard negatives | Keep under `/tmp` or ignored run paths until a reviewed result is promoted. | Generated reports and metrics may be released. Candidate source or diffs derived from external repos inherit the source repository's local-only classification unless cleared. |
| External repo snapshots | Git clones, source files, tests, docs, vendored examples | Retain as reproducible local clones pinned by URL and commit SHA. | Do not redistribute raw snapshots in `j3` releases. Release manifest refs, checksums, license metadata, and reproduction commands instead. |

## Mandatory Provenance Fields

Every durable training row or manifest entry must include these common fields:

- `record_id`: stable unique ID that does not encode the expected label.
- `schema_version`: manifest schema version.
- `artifact_class`: one of `scratch`, `checked_in_example`,
  `release_archive`, `synthetic`, `issue_pr`, `generated`, or
  `external_snapshot`.
- `source_kind`: `repo_code`, `repo_docs`, `issue_pr`, `candidate`,
  `synthetic_prompt`, `validation`, `teacher_label`, or `local_knowledge`.
- `source_uri`: canonical URL or local path template.
- `source_ref`: commit SHA, tag, archive version, issue/PR number, run ID, or
  generator version.
- `retrieved_at`: UTC timestamp for external retrievals or local capture time.
- `captured_by`: command, tool, script, or manual process that created the row.
- `review_status`: `unreviewed`, `reviewed`, `rejected`, or
  `release_cleared`.
- `license_spdx`: SPDX ID when known, otherwise `NOASSERTION`,
  `NO_LICENSE`, or `NOT_APPLICABLE`.
- `license_url`: URL or path for the governing license when available.
- `terms_url`: hosting or source terms URL when relevant.
- `redistribution_class`: `redistributable`, `metadata_only`,
  `local_only`, or `excluded`.
- `retention_class`: `scratch`, `durable_local`, `checked_in`, or
  `release`.
- `split`: `train`, `validation`, `test`, `calibration`, `heldout`, or
  `excluded`.
- `split_basis`: repository/task/prompt/template family keys used to assign the
  split.
- `checksum_algorithm`: normally `sha256`.
- `content_checksum`: checksum of the exact raw or normalized content used.
- `normalized_checksum`: checksum after documented normalization, if any.
- `pii_secret_scan`: scan status, tool, timestamp, and result.
- `exclusion_reasons`: empty list or concrete reasons such as
  `license_unknown`, `terms_unknown`, `secret_detected`, `generated_vendor`,
  `large_raw_external_payload`, `accepted_label_leakage`, or
  `teacher_provenance_missing`.

Additional required fields by source kind:

| Source kind | Required fields |
| --- | --- |
| Raw code | `provider`, `owner`, `repo`, `clone_url`, `commit_sha`, `file_path`, `blob_sha`, `language`, `repo_license_spdx`, `generated_or_vendor_flag`, `submodule_flag`, `snapshot_manifest_checksum` |
| Docs | `doc_url_or_path`, `doc_version_or_ref`, `section_id`, `doc_license_spdx`, `excerpt_policy`, `excerpt_checksum`, `retrieval_method` |
| Issues/PRs | `provider`, `owner`, `repo`, `issue_numbers`, `pr_numbers`, `issue_urls`, `pr_urls`, `base_ref`, `merge_or_head_ref`, `linked_diff_url`, `text_fields_present`, `comment_count`, `review_status`, `terms_review_status` |
| Generated candidates | `candidate_id`, `candidate_generator`, `generator_version`, `input_record_ids`, `action_family`, `mutation_scope`, `candidate_after_checksum`, `candidate_diff_checksum`, `derived_from_records`, `validation_record_ids` |
| Synthetic prompts | `template_family`, `template_id`, `template_version`, `seed`, `generator_name`, `generator_version`, `source_family`, `human_seed_record_ids`, `synthetic_transform`, `teacher_assisted` |
| Validations | `validation_id`, `command`, `environment_fingerprint`, `repo_ref`, `candidate_id`, `started_at`, `duration_seconds`, `exit_code`, `stdout_checksum`, `stderr_checksum`, `result`, `flaky_label`, `timeout_seconds` |
| Teacher-assisted labels | `teacher_kind`, `teacher_model_or_tool`, `teacher_version`, `prompt_checksum`, `response_checksum`, `human_reviewer`, `review_decision`, `allowed_use`, `split_restriction`, `label_confidence` |

Teacher-assisted labels are allowed only for development review, triage, and
shadow-model supervision when their provenance is recorded. They must not enter
held-out tests, calibration gates, release claims, or product-routing decisions
unless a later policy explicitly approves that use.

## Checksum Discipline

All durable rows must be reproducible from checksummed inputs. Use SHA-256
unless a source system exposes an immutable stronger content hash.

- Raw files: checksum exact bytes, plus normalized text when normalization is
  used.
- Repository snapshots: record clone URL, commit SHA, default branch at
  retrieval time, and a manifest checksum over sorted file paths, file modes,
  and per-file checksums.
- Diffs and patches: checksum the normalized unified diff and record the
  normalization rules, including path prefix stripping, timestamp removal, and
  line-ending normalization.
- Validation logs: checksum stdout and stderr separately; do not store large
  raw logs in release archives unless reviewed.
- Generated candidates: checksum both candidate-after file content and the
  candidate diff.
- Synthetic rows: checksum the rendered row and the template input tuple
  `(template_id, template_version, seed, source_family)`.
- Release archives: include a top-level manifest checksum and per-artifact
  checksums; record which local-only inputs were used but excluded.

Rows with missing checksums are usable only as scratch analysis and must be
excluded from training manifests, eval manifests, and release archives.

## Split And Leakage Controls

Splits must be stable, deterministic, and assigned before model training or
ranking evaluation. A future durable manifest builder should implement these
controls as checks, not prose-only review.

- Repository overlap: the same `owner/repo` cannot appear in both training and
  held-out/test splits for the same evaluation claim. Calibration repos must be
  labeled separately from held-out repos.
- Task overlap: records with the same issue, PR, accepted diff, validation
  recipe, task ID, or materialized candidate lineage must share a split.
- Prompt overlap: paraphrases, expansions, and generated prompts derived from
  the same seed prompt or issue text must share a split.
- Template-family overlap: synthetic rows from the same template family must be
  split by family for generalization claims. A random row split is allowed only
  for template debugging and must be labeled as such.
- Local-knowledge overlap: knowledge extracted from a held-out repo may be used
  for that repo only when the product scenario explicitly allows repo-local
  inspection at inference time. It must not train a global model evaluated on
  that same held-out repo.
- Validation overlap: hidden-like checks generated from accepted tests or PR
  diffs must share the source task split and must be marked
  `accepted_structure_derived`.
- Label leakage: accepted diff paths, decoy labels, candidate names, PR titles,
  and known pass/fail fields must be excluded from feature inputs unless the
  task is explicitly label-auditing rather than model evaluation.

If any overlap rule is uncertain, assign `split: excluded` until reviewed.

## Release Policy

Release artifacts may include:

- `j3` source, project-owned tests, and project-owned synthetic examples.
- Compact manifests with source URLs, refs, checksums, license metadata, split
  labels, and review status.
- Aggregate metrics, residual labels, validation summaries, and model cards.
- Model checkpoints trained on allowed data, with a manifest of included and
  excluded source classes.
- Small snippets only when they are project-owned or explicitly license/terms
  cleared and necessary for reproducibility.

Release artifacts must not include:

- Raw external repository snapshots, full files, vendored packages, or cloned
  corpora.
- Raw issue/PR bodies, review comments, discussion threads, or raw patches from
  hosting sites unless explicitly cleared.
- Candidate-after snapshots or diffs derived from external repos unless
  explicitly cleared.
- Large raw validation logs, environment dumps, secrets, credentials, tokens,
  personal data, or machine-specific paths beyond documented reproducibility
  templates.
- Teacher prompts or responses when the teacher provider terms, reviewer, or
  allowed use are not recorded.
- Any row with `redistribution_class: local_only`, `metadata_only` raw payloads,
  or `excluded`.

Model release artifacts must include a data statement that names the manifest
version, source classes, split rules, checksum algorithm, excluded classes,
teacher-label policy, known leakage risks, and whether the model is
shadow-only or eligible for guarded use.

## Exclusion Rules

Exclude a record from durable training and release if any of these apply:

- License is missing, incompatible, or not reviewed for the intended use.
- Hosting terms are unknown for issue/PR text, comments, docs, or patches.
- Secret or personal-data scan fails or has not run for external text/logs.
- The source is generated, vendored, minified, compiled, binary, model weights,
  package lock data, or bulk examples without useful Python maintenance signal.
- The row cannot be regenerated from source refs and checksums.
- Split lineage is ambiguous or overlaps a held-out/test source.
- The row includes accepted-label leakage not explicitly marked for a leakage
  audit.
- Teacher-assisted labels lack teacher identity, version, checksums, or human
  review status.

Excluded records may remain in scratch notes for debugging, but they must not
be part of training, evaluation, release, or guarded product claims.

## Manifest Readiness Checklist

A future durable training manifest task should not start model training until
it can validate the following:

- Every row has the mandatory common fields and source-kind fields.
- Every raw or normalized payload has SHA-256 checksums.
- Every external source has license and terms metadata.
- Every row has `redistribution_class`, `retention_class`, `split`, and
  `split_basis`.
- Split checks reject repository, task, prompt, and template-family overlap.
- Local-only raw payloads are referenced by checksum and path template but not
  copied into release directories.
- Teacher-assisted labels are isolated from held-out gates and product claims.
- Release archives can be built from manifests while excluding raw external
  payloads.
