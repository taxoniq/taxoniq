"""Update data package versions and dependency pins for an NCBI BLAST snapshot."""

import argparse
from datetime import datetime
from pathlib import Path

import tomlkit
from packaging.requirements import Requirement
from packaging.utils import canonicalize_name


def update_versions(root, timestamp_file):
    timestamp = datetime.strptime(timestamp_file.read_text().strip(), "%Y-%m-%d-%H-%M-%S")
    version = f"{timestamp.year}.{timestamp.month}.{timestamp.day}"
    package_paths = sorted((root / "db_packages").glob("*/pyproject.toml"))
    documents = {path: tomlkit.loads(path.read_text()) for path in [root / "pyproject.toml", *package_paths]}
    package_names = {canonicalize_name(documents[path]["project"]["name"]) for path in package_paths}
    for path, document in documents.items():
        project = document["project"]
        if path in package_paths:
            project["version"] = version
        for index, dependency in enumerate(project.get("dependencies", [])):
            requirement = Requirement(dependency)
            if canonicalize_name(requirement.name) in package_names:
                operator = ">=" if path == root / "pyproject.toml" else "=="
                project["dependencies"][index] = f"{requirement.name} {operator} {version}"
        path.write_text(tomlkit.dumps(document), encoding="utf-8")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("timestamp_file", type=Path, help="NCBI BLAST latest-dir file")
    args = parser.parse_args()
    update_versions(Path(__file__).resolve().parents[1], args.timestamp_file)
