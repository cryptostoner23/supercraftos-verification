#!/usr/bin/env python3
"""Validate resolved Xcode compile/resource inputs after XcodeGen has run.

Checking YAML paths alone misses malformed PBXGroup parentage. Resolve the
actual project graph like Xcode, then require every source/resource input to
exist and every native app Swift source to belong to its compile phase.
"""
from __future__ import annotations

import argparse
from collections import defaultdict
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
GROUP_TYPES = {"PBXGroup", "PBXVariantGroup", "XCVersionGroup"}
INPUT_PHASES = {"PBXSourcesBuildPhase", "PBXResourcesBuildPhase"}


class ProjectValidationError(ValueError):
    pass


def validate_project(document: dict, project_directory: Path,
                     required_app_sources: set[Path] | None = None) -> dict[str, int]:
    objects = document["objects"]
    project = objects[document["rootObject"]]
    main_group = project["mainGroup"]
    source_root = (project_directory / project.get("projectDirPath", "")).resolve()
    parents: dict[str, list[str]] = defaultdict(list)
    for identifier, item in objects.items():
        if item.get("isa") in GROUP_TYPES:
            for child in item.get("children", []):
                parents[child].append(identifier)
    for child, memberships in parents.items():
        if len(memberships) > 1:
            item = objects[child]
            name = item.get("name", item.get("path", child))
            raise ProjectValidationError(f"{name}: belongs to multiple groups {memberships}")
    if parents.get(main_group):
        raise ProjectValidationError("The main group must not have a parent")

    resolved: dict[str, Path] = {}

    def resolve(identifier: str, visiting: frozenset[str] = frozenset()) -> Path:
        if identifier in visiting:
            raise ProjectValidationError(f"Cycle in source group hierarchy: {identifier}")
        if identifier in resolved:
            return resolved[identifier]
        item = objects[identifier]
        path = item.get("path", "")
        if "$(" in path or "${" in path:
            raise ProjectValidationError(f"Unresolved source path variable: {path}")
        tree = item.get("sourceTree", "<group>")
        if tree == "<absolute>":
            result = Path(path)
            if not result.is_absolute():
                raise ProjectValidationError(f"Absolute source reference has a relative path: {path}")
        elif tree == "SOURCE_ROOT":
            result = source_root / path
        elif tree == "<group>":
            if identifier == main_group:
                base = source_root
            else:
                if not parents.get(identifier):
                    raise ProjectValidationError(f"Source reference has no parent group: {path}")
                base = resolve(parents[identifier][0], visiting | {identifier})
            result = base / path
        else:
            raise ProjectValidationError(f"Unsupported source tree {tree}: {path}")
        resolved[identifier] = result.resolve()
        return resolved[identifier]

    input_count = 0
    target_count = 0
    app_sources: set[Path] | None = None
    for target_id in project.get("targets", []):
        target = objects[target_id]
        if target.get("isa") != "PBXNativeTarget":
            continue
        target_count += 1
        sources: set[Path] = set()
        for phase_id in target.get("buildPhases", []):
            phase = objects[phase_id]
            if phase.get("isa") not in INPUT_PHASES:
                continue
            for build_file_id in phase.get("files", []):
                build_file = objects[build_file_id]
                reference = build_file.get("fileRef")
                if not reference:
                    raise ProjectValidationError(f"{target['name']}: build input has no file reference")
                path = resolve(reference)
                if not path.exists():
                    raise ProjectValidationError(f"{target['name']}: missing {phase['isa']} input {path}")
                if phase["isa"] == "PBXSourcesBuildPhase":
                    if path in sources:
                        raise ProjectValidationError(f"{target['name']}: duplicate compile input {path}")
                    sources.add(path)
                input_count += 1
        if target["name"] == "SuperCraftOS":
            app_sources = sources
    if not input_count:
        raise ProjectValidationError("The generated project contains no source/resource inputs")
    if required_app_sources is not None:
        if app_sources is None:
            raise ProjectValidationError("The SuperCraftOS app target is missing")
        expected = {path.resolve() for path in required_app_sources}
        if app_sources != expected:
            missing = sorted(str(path) for path in expected - app_sources)
            extra = sorted(str(path) for path in app_sources - expected)
            raise ProjectValidationError(f"App compile membership mismatch: missing={missing}, unexpected={extra}")
    return {"targets": target_count, "inputs": input_count}


def required_app_sources(root: Path) -> set[Path]:
    dist = root / "ios_app_dist"
    bundle = dist / "YourApp.swiftpm"
    return {bundle / "App.swift",
            root / "swift-verification/Sources/ControlCore/KeyboardCatalog.swift",
            *(bundle / path.name for path in dist.glob("*.swift"))}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("project", type=Path)
    args = parser.parse_args()
    project = args.project.resolve()
    # macOS plutil understands the actual OpenStep pbxproj serialization.
    raw = subprocess.check_output(["plutil", "-convert", "json", "-o", "-", str(project / "project.pbxproj")])
    try:
        result = validate_project(json.loads(raw), project.parent, required_app_sources(ROOT))
    except (ProjectValidationError, KeyError) as error:
        print(f"error: generated Xcode project is invalid: {error}", file=sys.stderr)
        return 1
    print(f"Validated generated Xcode graph: {result['targets']} targets, {result['inputs']} source/resource inputs")
    return 0


if __name__ == "__main__":
    sys.exit(main())
