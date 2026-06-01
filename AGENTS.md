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
- `src/pipeline.py` — TBPipeline with auto-training loop
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

## Important Paths (Docker/HF Space)
- Backend root: `/app/backend/`
- Frontend dist: `/app/frontend/dist/`
- Templates: `/app/src/generation/templates/`
- Output: `/app/output/`

## Known Issues
- `SpecFeatures.from_spec()` in coverage_predictor.py may fail if spec object doesn't have expected attributes (handled by heuristic fallback)
- V2 model's `_use_llm` flag defaults to False — coverage-driven hybrid path only activates when `use_llm=True`
