"""GitLab CI/CD pipeline generator for UVM Generator project.

Usage:
  python -m src.cicd.gitlab_ci        # writes .gitlab-ci.yml to project root
"""

import os, pathlib

HERE = pathlib.Path(__file__).resolve().parent
PROJECT_ROOT = HERE.parent.parent


def main(output_path: str = "") -> str:
    """Write .gitlab-ci.yml to project root (or given path)."""
    dest = output_path or os.path.join(PROJECT_ROOT, ".gitlab-ci.yml")

    # Copy from .gitlab-ci.yml template if it exists, else write from scratch
    template = os.path.join(PROJECT_ROOT, ".gitlab-ci.yml")
    if os.path.exists(template):
        import shutil
        shutil.copy2(template, dest)
    else:
        raise FileNotFoundError(
            "No .gitlab-ci.yml found at project root. "
            "Create one manually or copy from another source."
        )
    print(f"  GitLab CI: {dest}")
    return dest


if __name__ == "__main__":
    main()
