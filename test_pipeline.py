"""Quick local test of UVM generation pipeline."""
import sys, json
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from src.config import PipelineConfig, GenerationConfig
from src.data.core_parser import CoreParser
from src.data.preprocessor import SpecPreprocessor
from src.models.template_model import TemplateModel

CORE = Path("configs/uart16550-1.5.core")
TMPL = Path("src/generation/templates")

def main():
    # 1. Parse .core → DesignSpec
    raw = CoreParser().parse(CORE.read_text(encoding="utf-8"))
    spec = SpecPreprocessor().preprocess(raw)
    from src.config import DesignSpec
    design_spec = DesignSpec(**spec)

    # 2. PipelineConfig
    cfg = PipelineConfig(
        generation=GenerationConfig(
            templates_dir=str(TMPL.resolve()),
            output_dir="output",
            overwrite=True,
        )
    )

    # 3. TemplateModel
    model = TemplateModel(templates_dir=str(TMPL.resolve()))
    train_meta = model.train([design_spec])
    print(f"Model trained: {train_meta['template_count']} templates\n")

    # 4. Generate
    generated = model.predict(design_spec, cfg)

    # 5. Print and show requested files
    requested = ["sequence.sv", "coverage_collector.sv", "protocol_checker.sv"]
    print("=" * 60)
    for pat, path in generated.items():
        print(f"  {pat:45s} -> {path}")
    print("=" * 60)

    matched = []
    for pat, path in generated.items():
        for r in requested:
            base = r.replace("{name}", design_spec.design_name).replace("_", "_")
            r2 = r.replace(".sv", f"_{design_spec.design_name}.sv")
            if r in pat or r2 in pat or base in pat:
                matched.append(path)
                break

    print(f"\nGenerated {len(generated)} files total.")
    print(f"Requested file paths: {json.dumps(matched, indent=2)}")
    print(f"All output dir: {Path('output').resolve()}")

if __name__ == "__main__":
    main()
