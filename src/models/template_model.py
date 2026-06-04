from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Dict, List, Optional

from jinja2 import Environment, FileSystemLoader

from src.config import DesignSpec, PipelineConfig
from src.models.base_model import GenerationModel


class TemplateModel(GenerationModel):
    FUSESOC_MAP = {
        "{name}.core": "fusesoc.core.j2",
    }

    MAKEFILE_MAP = {
        "Makefile": "Makefile.j2",
    }

    TEMPLATE_MAP = {
        "env/{name}_env.sv": "env.sv.j2",
        "env/{name}_scoreboard.sv": "scoreboard.sv.j2",
        "env/{name}_coverage_collector.sv": "coverage_collector.sv.j2",
        "agent/{name}_driver.sv": "driver.sv.j2",
        "agent/{name}_monitor.sv": "monitor.sv.j2",
        "agent/{name}_sequencer.sv": "sequencer.sv.j2",
        "agent/{name}_sequence_item.sv": "sequence_item.sv.j2",
        "sequences/{name}_sequence.sv": "sequence.sv.j2",
        "tests/{name}_test.sv": "test.sv.j2",
        "sequences/{name}_reg_model_adapter.sv": "reg_model_adapter.sv.j2",
        "sequences/{name}_register_info_pkg.sv": "register_info_pkg.sv.j2",
        "{name}_reg_block.sv": "reg_block.sv.j2",
        "{name}_interface.sv": "interface.sv.j2",
        "testbench.sv": "testbench.sv.j2",
        "rtl/protocol_core.v": "rtl/protocol_core.v.j2",
    }

    RTL_MAP = {
        "rtl/protocol_core.v": "rtl/protocol_core.v.j2",
    }

    PROTOCOL_CHECKER_MAP = {
        "protocol_checker_{name}.sv": "protocol_checker.sv.j2",
    }

    ASSERTION_MAP = {
        "assertions_{name}.sv": "assertions.sv.j2",
    }

    CALLBACK_MAP = {
        "callback_{name}.sv": "callback.sv.j2",
    }

    FACTORY_OVERRIDE_MAP = {
        "factory_overrides_{name}.sv": "factory_overrides.sv.j2",
    }

    VIRTUAL_SEQR_MAP = {
        "virtual_sequencer_{name}.sv": "virtual_sequencer.sv.j2",
    }

    COVERAGE_SEQ_MAP = {
        "regression_{name}.sv": "regression_seq.sv.j2",
    }

    COMPILE_F = "compile.f"

    def __init__(self, name: str = "template_model", templates_dir: Optional[str] = None):
        super().__init__(name)
        self.templates_dir = templates_dir
        self._metadata: Dict[str, Any] = {}

    def train(self, specs: List[DesignSpec]) -> Dict[str, Any]:
        if not self.templates_dir:
            self.templates_dir = os.path.join(
                os.path.dirname(__file__), "..", "..", "src", "generation", "templates"
            )
        tmpl_dir = Path(self.templates_dir)
        if not tmpl_dir.exists():
            raise FileNotFoundError(f"Templates directory not found: {tmpl_dir}")

        available = list(tmpl_dir.glob("**/*.j2"))
        self._metadata = {
            "model_type": "template",
            "template_count": len(available),
            "templates": [str(f.relative_to(tmpl_dir)) for f in available],
            "trained_on_specs": len(specs),
            "source": str(tmpl_dir),
        }
        self._is_trained = True
        return self._metadata

    def predict(self, spec: DesignSpec, cfg: PipelineConfig,
                extra_seqs: Optional[List[str]] = None) -> Dict[str, str]:
        if not self._is_trained:
            raise RuntimeError("Model not trained. Call train() first.")
        if not self.templates_dir or not Path(self.templates_dir).exists():
            raise FileNotFoundError(f"Templates directory unavailable: {self.templates_dir}")

        env = Environment(loader=FileSystemLoader(self.templates_dir))
        name = spec.design_name
        output_dir = Path(cfg.generation.output_dir) / f"{name}_tb"
        output_dir.mkdir(parents=True, exist_ok=True)

        for subdir in ["sequences", "tests", "env"]:
            (output_dir / subdir).mkdir(parents=True, exist_ok=True)

        generated: Dict[str, str] = {}

        for out_pattern, template_file in self.TEMPLATE_MAP.items():
            out_name = out_pattern.format(name=name)
            tmpl = env.get_template(template_file)
            content = tmpl.render(spec=spec)
            out_path = output_dir / out_name
            if out_path.exists() and not cfg.generation.overwrite:
                import logging
                logging.getLogger("uvmgen").warning("Skipping existing: %s", out_name)
                continue
            out_path.write_text(content, encoding="utf-8")
            generated[out_name] = str(out_path)

        # Factory override examples
        for out_pattern, template_file in self.FACTORY_OVERRIDE_MAP.items():
            out_name = out_pattern.format(name=name)
            tmpl = env.get_template(template_file)
            content = tmpl.render(spec=spec)
            out_path = output_dir / out_name
            if out_path.exists() and not cfg.generation.overwrite:
                continue
            out_path.write_text(content, encoding="utf-8")
            generated[out_name] = str(out_path)

        # Callback classes
        for out_pattern, template_file in self.CALLBACK_MAP.items():
            out_name = out_pattern.format(name=name)
            tmpl = env.get_template(template_file)
            content = tmpl.render(spec=spec)
            out_path = output_dir / out_name
            if out_path.exists() and not cfg.generation.overwrite:
                continue
            out_path.write_text(content, encoding="utf-8")
            generated[out_name] = str(out_path)

        # Virtual sequencer
        for out_pattern, template_file in self.VIRTUAL_SEQR_MAP.items():
            out_name = out_pattern.format(name=name)
            tmpl = env.get_template(template_file)
            content = tmpl.render(spec=spec)
            out_path = output_dir / out_name
            if out_path.exists() and not cfg.generation.overwrite:
                continue
            out_path.write_text(content, encoding="utf-8")
            generated[out_name] = str(out_path)

        # Protocol checker
            out_name = out_pattern.format(name=name)
            tmpl = env.get_template(template_file)
            content = tmpl.render(spec=spec)
            out_path = output_dir / out_name
            if out_path.exists() and not cfg.generation.overwrite:
                continue
            out_path.write_text(content, encoding="utf-8")
            generated[out_name] = str(out_path)

        # Assertions
        for out_pattern, template_file in self.ASSERTION_MAP.items():
            out_name = out_pattern.format(name=name)
            tmpl = env.get_template(template_file)
            content = tmpl.render(spec=spec)
            out_path = output_dir / out_name
            if out_path.exists() and not cfg.generation.overwrite:
                continue
            out_path.write_text(content, encoding="utf-8")
            generated[out_name] = str(out_path)

        # RTL files
        rtl_dir = output_dir / "rtl"
        rtl_dir.mkdir(parents=True, exist_ok=True)
        for out_name, template_file in self.RTL_MAP.items():
            tmpl = env.get_template(template_file)
            content = tmpl.render(spec=spec)
            out_path = output_dir / out_name
            if out_path.exists() and not cfg.generation.overwrite:
                continue
            out_path.write_text(content, encoding="utf-8")
            generated[out_name] = str(out_path)

        # Extra coverage-driven sequences
        if extra_seqs:
            seq_dir = output_dir / "sequences"
            seq_dir.mkdir(parents=True, exist_ok=True)
            for i, seq_sv in enumerate(extra_seqs):
                seq_name = f"cover_seq_v{cfg.generation.iteration}_{i}.sv"
                seq_path = seq_dir / seq_name
                seq_path.write_text(seq_sv, encoding="utf-8")
                generated[str(seq_path)] = str(seq_path)

        # Regression sequence
        for out_pattern, template_file in self.COVERAGE_SEQ_MAP.items():
            out_name = out_pattern.format(name=name)
            tmpl = env.get_template(template_file)
            content = tmpl.render(spec=spec)
            out_path = output_dir / out_name
            out_path.write_text(content, encoding="utf-8")
            generated[out_name] = str(out_path)

        # TCL simulation script
        try:
            tmpl = env.get_template("tcl_sim.tcl.j2")
            tcl_path = output_dir / f"sim_{name}.tcl"
            tcl_path.write_text(tmpl.render(spec=spec), encoding="utf-8")
            generated[tcl_path.name] = str(tcl_path)
        except Exception:
            pass

        # compile.f
        compile_path = output_dir / self.COMPILE_F
        try:
            tmpl_compile = env.get_template("compile.f.j2")
            compile_content = tmpl_compile.render(spec=spec)
            compile_path.write_text(compile_content, encoding="utf-8")
        except Exception:
            with open(compile_path, "w", encoding="utf-8") as f:
                f.write(f"// Compile list for {name}\n")
                f.write("+define+UVM_NO_DPI\n")
                for sv_name in generated:
                    if sv_name.startswith("rtl/"):
                        f.write(f"{sv_name}\n")
                for sv_name in generated:
                    if sv_name.endswith(".sv") and not sv_name.startswith("rtl/"):
                        f.write(f"{sv_name}\n")
        generated[str(self.COMPILE_F)] = str(compile_path)

        # Makefile
        for out_pattern, template_file in self.MAKEFILE_MAP.items():
            out_name = out_pattern.format(name=name)
            try:
                tmpl = env.get_template(template_file)
                make_path = output_dir / out_name
                make_path.write_text(tmpl.render(spec=spec), encoding="utf-8")
                generated[out_name] = str(make_path)
            except Exception:
                pass

        # FuseSoC .core file
        for out_pattern, template_file in self.FUSESOC_MAP.items():
            out_name = out_pattern.format(name=name)
            try:
                tmpl = env.get_template(template_file)
                core_path = output_dir / out_name
                core_path.write_text(tmpl.render(spec=spec), encoding="utf-8")
                generated[out_name] = str(core_path)
            except Exception:
                pass

        return generated

    def save(self, path: str) -> None:
        save_dir = Path(path)
        save_dir.mkdir(parents=True, exist_ok=True)
        meta = {
            "name": self.name,
            "templates_dir": self.templates_dir,
            "metadata": self._metadata,
        }
        (save_dir / "model_metadata.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")

    @classmethod
    def load(cls, path: str) -> "TemplateModel":
        meta_path = Path(path) / "model_metadata.json"
        if not meta_path.exists():
            raise FileNotFoundError(f"Model metadata not found: {meta_path}")
        meta = json.loads(meta_path.read_text())
        model = cls(name=meta["name"], templates_dir=meta["templates_dir"])
        model._metadata = meta["metadata"]
        model._is_trained = True
        return model
