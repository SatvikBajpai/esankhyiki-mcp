#!/usr/bin/env python3
"""
Validate that the YAML-backed registry reproduces the ORIGINAL hardcoded
dataset structures from mospi_server.py.

Source of truth for the "expected" side is the origin/main mospi_server.py:
the literals VALID_DATASETS, DATASET_SWAGGER and DATASETS_REQUIRING_INDICATOR
are parsed straight out of that file via the ast module (no import, no
execution of the server).

The "actual" side is mospi/registry.py, which builds the same structures from
registry/datasets.yaml.

Checks (all membership-exact):
    1. VALID_DATASETS              - same codes, same order.
    2. DATASETS_REQUIRING_INDICATOR - same set of codes.
    3. DATASET_SWAGGER             - for every code in VALID_DATASETS, the
                                     (swagger_file, data_endpoint) tuple matches.

Note on CPI_GROUP / CPI_ITEM: the original DATASET_SWAGGER contains two helper
keys (CPI_GROUP, CPI_ITEM) that are NOT datasets in VALID_DATASETS. They are
internal routing aliases for CPI and are intentionally not modelled as registry
records, so the comparison restricts DATASET_SWAGGER to the VALID_DATASETS codes.

Exit code 0 on PASS, 1 on FAIL.
"""

import ast
import os
import subprocess
import sys

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Make `import mospi.registry` work when run from anywhere.
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)


def _load_origin_main_server_source() -> str:
    """Return origin/main:mospi_server.py source as text."""
    result = subprocess.run(
        ["git", "-C", REPO_ROOT, "show", "origin/main:mospi_server.py"],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise RuntimeError(
            "Could not read origin/main:mospi_server.py via git show:\n"
            + result.stderr
        )
    return result.stdout


def _parse_top_level_assign(tree: ast.Module, name: str):
    """Return the literal value of a module-level assignment `name = <literal>`."""
    for node in tree.body:
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id == name:
                    return ast.literal_eval(node.value)
    raise KeyError(f"Top-level assignment {name!r} not found in source.")


def _parse_original_structures():
    """Parse the three hardcoded structures out of origin/main mospi_server.py."""
    src = _load_origin_main_server_source()
    tree = ast.parse(src)
    valid = _parse_top_level_assign(tree, "VALID_DATASETS")
    swagger = _parse_top_level_assign(tree, "DATASET_SWAGGER")
    requiring = _parse_top_level_assign(tree, "DATASETS_REQUIRING_INDICATOR")
    # Normalize DATASET_SWAGGER tuples (literal_eval yields tuples already).
    swagger = {k: tuple(v) for k, v in swagger.items()}
    return valid, swagger, requiring


def main() -> int:
    import mospi.registry as registry

    orig_valid, orig_swagger, orig_requiring = _parse_original_structures()

    failures = []

    # 1. VALID_DATASETS - exact (order-sensitive) match.
    reg_valid = list(registry.VALID_DATASETS)
    if reg_valid != orig_valid:
        only_orig = [c for c in orig_valid if c not in reg_valid]
        only_reg = [c for c in reg_valid if c not in orig_valid]
        order_only = (not only_orig) and (not only_reg)
        failures.append(
            "VALID_DATASETS mismatch:\n"
            f"    only in original: {only_orig}\n"
            f"    only in registry: {only_reg}\n"
            f"    order differs only: {order_only}"
        )

    # 2. DATASETS_REQUIRING_INDICATOR - set equality.
    reg_req = set(registry.DATASETS_REQUIRING_INDICATOR)
    orig_req = set(orig_requiring)
    if reg_req != orig_req:
        failures.append(
            "DATASETS_REQUIRING_INDICATOR mismatch:\n"
            f"    only in original: {sorted(orig_req - reg_req)}\n"
            f"    only in registry: {sorted(reg_req - orig_req)}"
        )

    # 3. DATASET_SWAGGER - per-code (swagger_file, data_endpoint) match.
    #    Restrict the original to real datasets (drop CPI_GROUP / CPI_ITEM aliases).
    orig_swagger_datasets = {
        code: orig_swagger[code] for code in orig_valid if code in orig_swagger
    }
    missing_in_orig = [c for c in orig_valid if c not in orig_swagger]
    if missing_in_orig:
        failures.append(
            f"Original DATASET_SWAGGER is missing codes from VALID_DATASETS: "
            f"{missing_in_orig}"
        )

    reg_swagger = dict(registry.DATASET_SWAGGER)
    swagger_diffs = []
    for code in orig_valid:
        expected = orig_swagger_datasets.get(code)
        actual = reg_swagger.get(code)
        if actual != expected:
            swagger_diffs.append(
                f"    {code}: original={expected!r} registry={actual!r}"
            )
    # Extra keys in registry that are not real datasets would also be a problem.
    extra_in_reg = sorted(set(reg_swagger) - set(orig_valid))
    if extra_in_reg:
        swagger_diffs.append(f"    extra codes in registry: {extra_in_reg}")
    if swagger_diffs:
        failures.append("DATASET_SWAGGER mismatch:\n" + "\n".join(swagger_diffs))

    # Report.
    print("=" * 70)
    print("Registry validation against origin/main mospi_server.py")
    print("=" * 70)
    print(f"  registry file:        {registry.registry_path()}")
    print(f"  datasets in registry: {len(reg_valid)}")
    print(f"  datasets in original: {len(orig_valid)}")
    print(f"  requires_indicator:   {len(reg_req)} (registry) / {len(orig_req)} (original)")
    print("-" * 70)

    if failures:
        print("RESULT: FAIL")
        print("-" * 70)
        for f in failures:
            print(f)
        print("=" * 70)
        return 1

    print("RESULT: PASS")
    print("  VALID_DATASETS:              exact match (order preserved)")
    print("  DATASETS_REQUIRING_INDICATOR: exact set match")
    print("  DATASET_SWAGGER:             every code's (swagger_file, data_endpoint) matches")
    print("=" * 70)
    return 0


if __name__ == "__main__":
    sys.exit(main())
