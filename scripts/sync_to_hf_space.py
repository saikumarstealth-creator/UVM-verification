from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

try:
    from huggingface_hub import HfApi, login
    HAS_HF = True
except ImportError:
    HAS_HF = False


def sync_model_registry(
    registry_dir: str,
    space_id: str,
    hf_token: Optional[str] = None,
    target_dir: str = "model_registry",
    latest_only: bool = False,
    dry_run: bool = False,
) -> Dict[str, Any]:
    if not HAS_HF:
        print("ERROR: huggingface-hub not installed. Run: pip install huggingface-hub")
        return {"status": "error", "message": "huggingface-hub not installed"}

    registry_path = Path(registry_dir)
    if not registry_path.is_dir():
        return {"status": "error", "message": f"Registry dir not found: {registry_dir}"}

    if hf_token:
        login(token=hf_token)
        print(f"Logged in to HF with token (len={len(hf_token)})")
    else:
        print("No HF token provided, using cached credentials")

    api = HfApi()

    versions_file = registry_path / "versions.jsonl"
    stages_file = registry_path / "stages.json"
    summary_file = registry_path / "training_summary.json"

    uploads = []
    skipped = 0

    version_dirs = sorted(
        [d for d in registry_path.iterdir() if d.is_dir() and d.name.startswith("v")],
        key=lambda x: [int(p) for p in x.name[1:].split(".") if p.isdigit()] if x.name[1:].split(".")[0].isdigit() else [0],
    )

    if latest_only and version_dirs:
        version_dirs = [version_dirs[-1]]
        print(f"Latest-only mode: syncing {version_dirs[0].name}")

    print(f"Syncing {len(version_dirs)} version directories to HF Space {space_id}/{target_dir}")

    for version_dir in version_dirs:
        remote_path = f"{target_dir}/{version_dir.name}"
        local_path = str(version_dir)

        if dry_run:
            print(f"  [DRY-RUN] Would upload {local_path}/ -> {remote_path}/")
            uploads.append({"local": local_path, "remote": remote_path, "status": "dry-run"})
            continue

        try:
            api.upload_folder(
                repo_id=space_id,
                folder_path=local_path,
                path_in_repo=remote_path,
                repo_type="space",
                token=hf_token,
                ignore_patterns=["__pycache__/*", "*.pyc", ".gitkeep"],
            )
            print(f"  Uploaded {version_dir.name} -> {remote_path}")
            uploads.append({"local": local_path, "remote": remote_path, "status": "uploaded"})
        except Exception as e:
            print(f"  FAILED {version_dir.name}: {e}")
            uploads.append({"local": local_path, "remote": remote_path, "status": "failed", "error": str(e)})
            skipped += 1

    meta_files = [
        (versions_file, f"{target_dir}/versions.jsonl"),
        (stages_file, f"{target_dir}/stages.json"),
        (summary_file, f"{target_dir}/training_summary.json"),
    ]

    for local, remote in meta_files:
        if dry_run:
            print(f"  [DRY-RUN] Would upload {local} -> {remote}")
            continue
        if local.exists():
            try:
                api.upload_file(
                    repo_id=space_id,
                    path_or_fileobj=str(local),
                    path_in_repo=remote,
                    repo_type="space",
                    token=hf_token,
                )
                print(f"  Uploaded {local.name} -> {remote}")
            except Exception as e:
                print(f"  FAILED {local.name}: {e}")

    result = {
        "status": "success",
        "space_id": space_id,
        "total_versions": len(version_dirs),
        "uploaded": len([u for u in uploads if u.get("status") == "uploaded"]),
        "failed": len([u for u in uploads if u.get("status") == "failed"]),
        "skipped": skipped,
        "uploads": uploads,
    }

    if not dry_run:
        result_path = registry_path / "hf_sync_result.json"
        with open(result_path, "w") as f:
            json.dump(result, f, indent=2)
        print(f"Sync result saved to {result_path}")

    return result


def main() -> None:
    parser = argparse.ArgumentParser(description="Sync model registry to HF Space")
    parser.add_argument("--registry-dir", default="model_registry", help="Local model registry directory")
    parser.add_argument("--space-id", default="skumar889/semiconductor-pipeline", help="HF Space ID")
    parser.add_argument("--hf-token", default=None, help="Hugging Face token (or use HF_TOKEN env var)")
    parser.add_argument("--target-dir", default="model_registry", help="Target directory in HF Space")
    parser.add_argument("--latest-only", action="store_true", help="Only sync the latest version")
    parser.add_argument("--dry-run", action="store_true", help="Preview without uploading")

    args = parser.parse_args()

    token = args.hf_token or os.environ.get("HF_TOKEN")
    if not token and not args.dry_run:
        print("WARNING: No HF token provided. Set HF_TOKEN env var or pass --hf-token")
        print("Continuing with cached credentials...")

    result = sync_model_registry(
        registry_dir=args.registry_dir,
        space_id=args.space_id,
        hf_token=token,
        target_dir=args.target_dir,
        latest_only=args.latest_only,
        dry_run=args.dry_run,
    )

    print(f"\nSync complete: {result['status']}")
    if result.get("uploaded"):
        print(f"Uploaded {result['uploaded']} version(s)")
    if result.get("failed"):
        print(f"Failed {result['failed']} version(s)")


if __name__ == "__main__":
    main()
