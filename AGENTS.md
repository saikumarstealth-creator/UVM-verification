# UVM-Verification Project — Settings & State

## Project
- HF Space: `skumar889/semiconductor-pipeline` at `https://skumar889-semiconductor-pipeline.hf.space`
- GitHub: `saikumarstealth-creator/UVM-verification`
- Port: 7860 (Docker, HF Space)
- Frontend: Vite+React served as static files by FastAPI

## Generation Config Defaults (backend/schemas.py)
| Field | Default |
|---|---|
| design_name | (required) |
| protocol | (required) |
| model_type | "v2" |
| rl_strategy | "ucb" |
| enable_learning | true |
| strict_uvm | true |
| max_iterations | 1 |
| spec_yaml | (required) |

## ML Model Architecture
- **Tier 1**: TemplateModel — Jinja2 template rendering (fallback)
- **Tier 2**: EnhancedMLGenerationModelV2 — ensemble retrieval + RL + coverage-driven hybrid generation
  - `_select_generation_strategy()`: RL per-file-type Q-values aggregated, biased by coverage prediction
  - `_generate_by_retrieval()`: similarity search → SpecAdapter adaptation → validation
  - `_generate_by_llm()`: coverage-driven hybrid (generates targeted sequences for predicted gaps)
  - `_generate_by_template()`: Jinja2 fallback
  - RL: AdvancedReinforcementLearner with eligibility traces, experience replay, 4 exploration strategies (epsilon_greedy/softmax/UCB/thompson)
  - Coverage predictor: RandomForest + GBR + LinearRegression ensemble with Ridge meta-blender
- **Pipeline**: auto-training loop (generate → simulate → analyze → improve) up to max_iterations

## Key Files
- `src/models/coverage_predictor.py` — coverage prediction ensemble (15 features, 5000 synthetic samples)
- `src/models/enhanced_ml_model_v2.py` — main V2 model (1014 lines)
- `src/models/enhanced_ml_model.py` — V1 model (older, less sophisticated)
- `src/models/template_model.py` — Jinja2 template renderer
- `src/models/advanced_rl_learner.py` — RL with eligibility traces + experience replay
- `src/models/advanced_pattern_learner.py` — context-aware error pattern detection
- `src/models/similarity_index.py` — TF-IDF + structural similarity search
- `src/models/spec_adapter.py` — spec-to-spec adaptation with signal/register mapping
- `src/features/extractors.py` — SpecFeatureExtractor, RichSpecFeatureExtractor
- `src/pipeline.py` — TBPipeline with auto-training loop, SV check, quality score
- `src/evaluation/sv_checker.py` — Python-based SV syntax checker (no external tools needed)
- `src/evaluation/quality_score.py` — Composite quality score (completeness, syntax, RAL, coverage)
- `src/generation/engine.py` — GenerationEngine (model wrapper)
- `src/generation/templates/` — Jinja2 SV templates
- `backend/core/pipeline_manager.py` — HF Space backend pipeline orchestration
- `frontend/src/components/ConfigEditor.tsx` — UI generation config form
- `frontend/src/store/appStore.ts` — Zustand state store

## Key Decisions
- Replicate removed (free tier requires payment); all generation runs on HF Space CPU
- Coverage predictor uses synthetic training data (not real simulation feedback) — train on real data when available
- RL state: `{protocol}:{file_type}:{complexity_bucket}` (low/medium/high)
- Template files excluded from Docker via `.dockerignore`: `model_registry/`, `node_modules`, `__pycache__`, etc.
- **Phase 1 complete (Jun 2026)**: All 5 templates rewritten to be spec-driven — no more hallucinated registers
- `{% if p == "uart" %}` guards scope UART-specific blocks (scoreboard, sequence, test) cleanly
- SV syntax checker is Python-based (no iverilog/svlint dependency); runs on rendered `.sv` output

## Template Status (Post-Phase 2)
| Template | Status | Key Changes |
|---|---|---|
| `ral_model.sv.j2` | ✅ Spec-driven | Iterates `spec.registers` → register classes, block, adapter, predictor; no hardcoded UART names; `addr_bits` computed inline via `map\|max` (no `__setitem__` hack) |
| `coverage_collector.sv.j2` | ✅ Enhanced crosses | Added coverage crosses (baud×parity, baud×data_bits, parity×stop_bits, baud×frame); UART config CG with separate data_bits/stop_bits coverpoints |
| `scoreboard.sv.j2` | ✅ Record methods added | Added `record_tx()`, `record_rx()`, `record_error()`, `record_config()` for sequence→scoreboard integration |
| `sequence.sv.j2` | ✅ Production-grade | Response handling (`get_response`), helpers in `uart_base_seq` (no duplication), seq library, virtual seq, reset test, ASCII constraints, scoreboard record calls, factory override support |
| `sequence_item.sv.j2` | ✅ Enhanced | `uvm_object_utils_begin/end` with field macros, `error_type_e` enum, `do_print()`, `inject_error()` helper, `int unsigned delay` |
| `test.sv.j2` | ✅ UART tests expanded | Added `uart_reset_test`, `uart_virtual_test`; all UART-specific tests guarded by `{% if p == "uart" %}` |

## Pipeline additions (Jun 2026)
- **Step 6a2**: SV syntax check via `SVSyntaxChecker` — block structure, paren balance, type refs, protocol consistency, common pitfalls
- **Step 6a3**: Cross-file reference validation via `validate_generated_files()` — catches `reg_model.xxx` hallucinations where `xxx` not in spec registers; computes spec register/interf reference coverage
- **Step 6b**: AI quality score via `compute_quality_score()` — weighted composite including spec_coverage_score (35% weight); hallucination_penalty (-0.1 each, max -0.5)
- Results include `sv_check` dict, `quality_score` float, `cross_file_validation` dict (passed, hallucinations, spec_coverage)
- ZIP export at `GET /api/export-zip` — downloads all generated files as a single archive (wired to UI Download button)
- New files: `src/evaluation/cross_file_validator.py`

## Phase 2 Enhancements (Jun 2026) — AI Quality & UVM Completeness
- **sequence.sv.j2**: Major enhancement — response handling (`get_response`), duplicate helpers moved to `uart_base_seq` (reduces code 30-40%), sequence library (`uart_seq_lib`), virtual sequence (`uart_virtual_seq`), reset test (`uart_reset_test_seq`), ASCII constraint mode, scoreboard integration (`record_tx`/`record_rx`/`record_error`/`record_config`), `req`/`rsp` declarations
- **coverage_collector.sv.j2**: Added coverage crosses (`cross_baud_parity`, `cross_baud_data_bits`, `cross_parity_stop_bits`, `cross_baud_frame`), separate `cp_data_bits`/`cp_stop_bits` coverpoints
- **scoreboard.sv.j2**: Added `record_tx()`, `record_rx()`, `record_error()`, `record_config()` record methods for sequence integration
- **test.sv.j2**: Added `uart_reset_test` and `uart_virtual_test` classes
- **quality_score.py**: Enhanced with `sequence_score` metric, `to_dict()` (syntax/ral/coverage/sequence/overall scores), `generate_report()` JSON report method
- **pipeline.py**: Generates `ai_quality_report.json` and `coverage_summary.html` in output dir; sequence quality auto-detection from generated content

## Next Steps
1. Wire cross_file_validation results into React frontend metrics display
2. Guard hardcoded UART register references (`reg_model.lcr`, `reg_model.dll`, etc.) in scoreboard/sequence/test behind a check that those registers actually exist in the spec
3. Add more protocol templates (AXI4, AHB, Wishbone)
4. Generate architecture diagram from spec
5. Add register covergroups to the generated HTML coverage report

## Important Paths (Docker/HF Space)
- Backend root: `/app/backend/`
- Frontend dist: `/app/frontend/dist/`
- Templates: `/app/src/generation/templates/`
- Output: `/app/output/`

## Known Issues
- `SpecFeatures.from_spec()` in coverage_predictor.py may fail if spec object doesn't have expected attributes (handled by heuristic fallback)
- V2 model's `_use_llm` flag defaults to False — coverage-driven hybrid path only activates when `use_llm=True`
- SV `{N{1'b1}}` concatenation pattern clashes with Jinja2 `{{ }}` — use `'1` (SV fill-ones literal) instead in templates
- **Docker entrypoint is `backend.main:app`**, not `src.api.server:app` — changes to API must go in `backend/main.py`
