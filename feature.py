#!/usr/bin/env python3
"""
Feature Development CLI Tool

Manage feature development lifecycle:
- Create new features from template
- Track feature status
- Create feature branches
- Generate feature reports

Usage:
    python3 feature.py new <feature-name> [--app typing|math|reading|piano|all]
    python3 feature.py list [--status draft|in_progress|review|completed|archived]
    python3 feature.py status <feature-name>
    python3 feature.py update <feature-name> --status <new-status>
    python3 feature.py branch <feature-name>
    python3 feature.py report
"""

import argparse
import json
import os
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path

MODULE_DIR = Path(__file__).parent
FEATURES_DIR = MODULE_DIR / "features"
REGISTRY_FILE = FEATURES_DIR / "registry.json"
TEMPLATE_DIR = FEATURES_DIR / "_template"

VALID_STATUSES = ["draft", "in_progress", "review", "completed", "archived"]
VALID_APPS = ["typing", "math", "reading", "piano", "all", "core"]


def load_registry():
    """Load the feature registry."""
    if REGISTRY_FILE.exists():
        with open(REGISTRY_FILE) as f:
            return json.load(f)
    return {"features": {}, "metadata": {"last_updated": None}}


def save_registry(registry):
    """Save the feature registry."""
    registry["metadata"]["last_updated"] = datetime.now().isoformat()
    with open(REGISTRY_FILE, "w") as f:
        json.dump(registry, f, indent=2)


def slugify(name):
    """Convert feature name to slug."""
    return name.lower().replace(" ", "-").replace("_", "-")


def create_feature(name, app="all", description=""):
    """Create a new feature from template."""
    slug = slugify(name)
    feature_dir = FEATURES_DIR / slug

    if feature_dir.exists():
        print(f"Error: Feature '{slug}' already exists at {feature_dir}")
        return False

    # Create feature directory
    feature_dir.mkdir(parents=True)

    # Create feature spec file
    spec_content = f"""# {name}

## Status: Draft

## Overview

{description or 'Brief description of what this feature accomplishes.'}

## Target App(s): {app}

## Requirements

- [ ] Requirement 1
- [ ] Requirement 2
- [ ] Requirement 3

## Technical Design

### Database Changes

```sql
-- Add any schema changes needed
```

### API Endpoints

| Method | Endpoint | Purpose |
|--------|----------|---------|
| GET | /api/... | ... |
| POST | /api/... | ... |

### Frontend Changes

- [ ] Component/UI changes needed
- [ ] JavaScript changes needed

## Implementation Tasks

- [ ] Task 1
- [ ] Task 2
- [ ] Task 3

## Testing Plan

- [ ] Unit tests
- [ ] Integration tests
- [ ] Manual testing steps

## Rollout Plan

1. Implement in DEV
2. Test thoroughly
3. Deploy to QA
4. User acceptance testing
5. Production release

## Notes

_Add any additional notes, considerations, or discussions here._

---
Created: {datetime.now().strftime('%Y-%m-%d')}
Author:
Branch: feature/{slug}
"""

    (feature_dir / "spec.md").write_text(spec_content)

    # Create implementation notes file
    impl_content = f"""# {name} - Implementation Notes

## Progress Log

### {datetime.now().strftime('%Y-%m-%d')}
- Feature created

## Code Changes

List files modified/created:
-

## Issues Encountered

-

## Testing Results

-
"""
    (feature_dir / "implementation.md").write_text(impl_content)

    # Update registry
    registry = load_registry()
    registry["features"][slug] = {
        "name": name,
        "slug": slug,
        "app": app,
        "status": "draft",
        "created": datetime.now().isoformat(),
        "updated": datetime.now().isoformat(),
        "branch": f"feature/{slug}",
        "description": description,
    }
    save_registry(registry)

    print(f"Created feature: {slug}")
    print(f"  Directory: {feature_dir}")
    print(f"  Spec: {feature_dir / 'spec.md'}")
    print(f"  Branch: feature/{slug}")
    print()
    print("Next steps:")
    print(f"  1. Edit the spec: {feature_dir / 'spec.md'}")
    print(f"  2. Create branch: python3 feature.py branch {slug}")
    print(f"  3. Update status: python3 feature.py update {slug} --status in_progress")

    return True


def list_features(status_filter=None):
    """List all features."""
    registry = load_registry()
    features = registry.get("features", {})

    if not features:
        print("No features registered.")
        return

    # Group by status
    by_status = {}
    for slug, info in features.items():
        status = info.get("status", "draft")
        if status_filter and status != status_filter:
            continue
        if status not in by_status:
            by_status[status] = []
        by_status[status].append((slug, info))

    if not by_status:
        print(f"No features with status '{status_filter}'")
        return

    for status in VALID_STATUSES:
        if status not in by_status:
            continue
        print(f"\n## {status.upper().replace('_', ' ')}")
        print("-" * 40)
        for slug, info in by_status[status]:
            app = info.get("app", "all")
            name = info.get("name", slug)
            print(f"  [{app:8}] {slug:30} - {name}")


def show_status(feature_name):
    """Show detailed status of a feature."""
    slug = slugify(feature_name)
    registry = load_registry()
    features = registry.get("features", {})

    if slug not in features:
        print(f"Feature '{slug}' not found in registry.")
        return False

    info = features[slug]
    feature_dir = FEATURES_DIR / slug

    print(f"\n{'='*50}")
    print(f"Feature: {info.get('name', slug)}")
    print(f"{'='*50}")
    print(f"  Slug:        {slug}")
    print(f"  Status:      {info.get('status', 'unknown')}")
    print(f"  App:         {info.get('app', 'all')}")
    print(f"  Branch:      {info.get('branch', 'N/A')}")
    print(f"  Created:     {info.get('created', 'N/A')}")
    print(f"  Updated:     {info.get('updated', 'N/A')}")
    print(f"  Directory:   {feature_dir}")

    # Check if spec file exists and show requirements progress
    spec_file = feature_dir / "spec.md"
    if spec_file.exists():
        content = spec_file.read_text()
        total_tasks = content.count("- [ ]") + content.count("- [x]")
        completed = content.count("- [x]")
        if total_tasks > 0:
            pct = int(100 * completed / total_tasks)
            print(f"  Progress:    {completed}/{total_tasks} tasks ({pct}%)")

    return True


def update_status(feature_name, new_status):
    """Update feature status."""
    if new_status not in VALID_STATUSES:
        print(f"Invalid status. Must be one of: {', '.join(VALID_STATUSES)}")
        return False

    slug = slugify(feature_name)
    registry = load_registry()
    features = registry.get("features", {})

    if slug not in features:
        print(f"Feature '{slug}' not found in registry.")
        return False

    old_status = features[slug].get("status", "draft")
    features[slug]["status"] = new_status
    features[slug]["updated"] = datetime.now().isoformat()
    save_registry(registry)

    print(f"Updated '{slug}': {old_status} -> {new_status}")

    # Move to completed-features if completed
    if new_status == "completed":
        print("Consider moving to completed-features/ for archival.")

    return True


def create_branch(feature_name):
    """Create a git branch for the feature."""
    slug = slugify(feature_name)
    branch_name = f"feature/{slug}"

    # Check if branch exists
    result = subprocess.run(
        ["git", "branch", "--list", branch_name],
        capture_output=True,
        text=True,
        cwd=MODULE_DIR,
    )

    if branch_name in result.stdout:
        print(f"Branch '{branch_name}' already exists.")
        checkout = input("Switch to it? [y/N]: ").strip().lower()
        if checkout == "y":
            subprocess.run(["git", "checkout", branch_name], cwd=MODULE_DIR)
        return True

    # Create and checkout branch
    print(f"Creating branch: {branch_name}")
    subprocess.run(["git", "checkout", "-b", branch_name], cwd=MODULE_DIR)

    return True


def generate_report():
    """Generate a summary report of all features."""
    registry = load_registry()
    features = registry.get("features", {})

    print("\n" + "=" * 60)
    print("FEATURE DEVELOPMENT REPORT")
    print(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print("=" * 60)

    # Count by status
    status_counts = {}
    app_counts = {}
    for info in features.values():
        status = info.get("status", "draft")
        app = info.get("app", "all")
        status_counts[status] = status_counts.get(status, 0) + 1
        app_counts[app] = app_counts.get(app, 0) + 1

    print("\n## Summary")
    print(f"Total Features: {len(features)}")

    print("\n### By Status:")
    for status in VALID_STATUSES:
        count = status_counts.get(status, 0)
        if count:
            print(f"  {status:15} {count}")

    print("\n### By App:")
    for app, count in sorted(app_counts.items()):
        print(f"  {app:15} {count}")

    # List in_progress features
    in_progress = [(s, i) for s, i in features.items() if i.get("status") == "in_progress"]
    if in_progress:
        print("\n## Active Development")
        for slug, info in in_progress:
            print(f"  - {info.get('name', slug)} ({info.get('app', 'all')})")


def scan_existing_features():
    """Scan features directory and register untracked features."""
    registry = load_registry()
    existing = set(registry.get("features", {}).keys())

    for item in FEATURES_DIR.iterdir():
        if item.is_dir() and not item.name.startswith("_") and not item.name.startswith("."):
            slug = item.name
            if slug not in existing and slug != "completed-features":
                # Check for spec file
                spec_file = item / "spec.md"
                if not spec_file.exists():
                    spec_file = item / "feature.md"

                name = slug.replace("-", " ").title()
                status = "in_progress"

                # Try to extract status from spec
                if spec_file.exists():
                    content = spec_file.read_text()
                    if "Status: Completed" in content or "Status: Done" in content:
                        status = "completed"
                    elif "Status: Draft" in content:
                        status = "draft"

                registry["features"][slug] = {
                    "name": name,
                    "slug": slug,
                    "app": "all",
                    "status": status,
                    "created": datetime.now().isoformat(),
                    "updated": datetime.now().isoformat(),
                    "branch": f"feature/{slug}",
                    "description": "",
                }
                print(f"Registered existing feature: {slug}")

    save_registry(registry)


def main():
    parser = argparse.ArgumentParser(
        description="Feature Development CLI Tool",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python3 feature.py new "Dark Mode" --app all
  python3 feature.py new "Math Hints" --app math --description "Add hint system"
  python3 feature.py list --status in_progress
  python3 feature.py update dark-mode --status in_progress
  python3 feature.py branch dark-mode
  python3 feature.py report
        """,
    )

    subparsers = parser.add_subparsers(dest="command", help="Command to run")

    # new command
    new_parser = subparsers.add_parser("new", help="Create a new feature")
    new_parser.add_argument("name", help="Feature name")
    new_parser.add_argument(
        "--app",
        choices=VALID_APPS,
        default="all",
        help="Target app (default: all)",
    )
    new_parser.add_argument("--description", "-d", default="", help="Brief description")

    # list command
    list_parser = subparsers.add_parser("list", help="List features")
    list_parser.add_argument("--status", "-s", choices=VALID_STATUSES, help="Filter by status")

    # status command
    status_parser = subparsers.add_parser("status", help="Show feature status")
    status_parser.add_argument("name", help="Feature name or slug")

    # update command
    update_parser = subparsers.add_parser("update", help="Update feature status")
    update_parser.add_argument("name", help="Feature name or slug")
    update_parser.add_argument(
        "--status", "-s", choices=VALID_STATUSES, required=True, help="New status"
    )

    # branch command
    branch_parser = subparsers.add_parser("branch", help="Create/switch to feature branch")
    branch_parser.add_argument("name", help="Feature name or slug")

    # report command
    subparsers.add_parser("report", help="Generate feature report")

    # scan command
    subparsers.add_parser("scan", help="Scan and register existing features")

    args = parser.parse_args()

    if args.command == "new":
        create_feature(args.name, args.app, args.description)
    elif args.command == "list":
        list_features(args.status)
    elif args.command == "status":
        show_status(args.name)
    elif args.command == "update":
        update_status(args.name, args.status)
    elif args.command == "branch":
        create_branch(args.name)
    elif args.command == "report":
        generate_report()
    elif args.command == "scan":
        scan_existing_features()
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
