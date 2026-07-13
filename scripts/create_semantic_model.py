#!/usr/bin/env python3
"""
Create a Direct Lake semantic model over the ccg lakehouse tables.

Reads the onelake sync config (workspace + lakehouse names), resolves the
lakehouse's SQL endpoint via the fab CLI, generates a multi-table TMDL
definition (usage_daily, model_pricing, devices with relationships and
cost/token measures), and imports it into the workspace. Nothing is
hardcoded: any Fabric tenant, workspace, capacity, or lakehouse works as
long as `fab auth login` is signed in to it.

Usage:
    python3 scripts/create_semantic_model.py [--model-name "Claude Usage"]
        [--workspace W] [--lakehouse L] [--store-id]

Requirements:
    - fab CLI installed and authenticated (against YOUR tenant)
    - onelake provider configured (ccg sync setup --provider onelake),
      unless --workspace/--lakehouse are given
"""
import argparse
import json
import shutil
import subprocess
import sys
import tempfile
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.config.user_config import get_sync_config, set_sync_config  # noqa: E402

TABLES: dict[str, list[tuple[str, str]]] = {
    "usage_daily": [
        ("date", "dateTime"), ("device_id", "string"), ("model", "string"),
        ("folder", "string"), ("git_branch", "string"),
        ("records", "int64"), ("sessions", "int64"),
        ("input_tokens", "int64"), ("output_tokens", "int64"),
        ("cache_creation_tokens", "int64"), ("cache_read_tokens", "int64"),
        ("total_tokens", "int64"), ("last_updated", "dateTime"),
    ],
    "model_pricing": [
        ("model_name", "string"),
        ("input_price_per_mtok", "double"), ("output_price_per_mtok", "double"),
        ("cache_write_price_per_mtok", "double"), ("cache_read_price_per_mtok", "double"),
        ("last_updated", "string"), ("notes", "string"),
    ],
    "devices": [
        ("device_id", "string"), ("device_name", "string"), ("device_type", "string"),
        ("user_upn", "string"), ("organization", "string"), ("subscription", "string"),
        ("last_push_at", "dateTime"),
    ],
}

MEASURES: list[tuple[str, str, str]] = [
    ("Total Tokens", "SUM(usage_daily[total_tokens])", "#,0"),
    (
        "Est API Cost",
        "SUMX(\n"
        "    usage_daily,\n"
        "    DIVIDE(usage_daily[input_tokens], 1e6) * RELATED(model_pricing[input_price_per_mtok])\n"
        "        + DIVIDE(usage_daily[output_tokens], 1e6) * RELATED(model_pricing[output_price_per_mtok])\n"
        "        + DIVIDE(usage_daily[cache_creation_tokens], 1e6) * RELATED(model_pricing[cache_write_price_per_mtok])\n"
        "        + DIVIDE(usage_daily[cache_read_tokens], 1e6) * RELATED(model_pricing[cache_read_price_per_mtok])\n"
        ")",
        "\\$#,0.00",
    ),
    ("Total Sessions", "SUM(usage_daily[sessions])", "#,0"),
    ("Active Devices", "DISTINCTCOUNT(usage_daily[device_id])", "#,0"),
]

RELATIONSHIPS: list[tuple[str, str]] = [
    ("usage_daily.model", "model_pricing.model_name"),
    ("usage_daily.device_id", "devices.device_id"),
]


def fab(args: list[str]) -> str:
    fab_bin = shutil.which("fab")
    if not fab_bin:
        raise SystemExit("fab CLI not found on PATH. Install: uv tool install ms-fabric-cli")
    result = subprocess.run([fab_bin, *args], capture_output=True, text=True, timeout=120)
    if result.returncode != 0:
        raise SystemExit(f"fab {' '.join(args)} failed: {result.stderr.strip()[:300]}")
    return result.stdout.strip()


def table_tmdl(name: str) -> str:
    lines = [f"table '{name}'", f"\tlineageTag: {uuid.uuid4()}",
             f"\tsourceLineageTag: [dbo].[{name}]", ""]
    if name == "usage_daily":
        for measure_name, expr, fmt in MEASURES:
            lines.append(f"\tmeasure '{measure_name}' =")
            for expr_line in expr.split("\n"):
                lines.append(f"\t\t\t{expr_line}")
            lines += [f"\t\tformatString: {fmt}", f"\t\tlineageTag: {uuid.uuid4()}", ""]
    for col, dtype in TABLES[name]:
        lines += [
            f"\tcolumn '{col}'",
            f"\t\tdataType: {dtype}",
            f"\t\tlineageTag: {uuid.uuid4()}",
            f"\t\tsourceLineageTag: {col}",
            "\t\tsummarizeBy: none",
            f"\t\tsourceColumn: {col}",
            "",
            "\t\tannotation SummarizationSetBy = Automatic",
            "",
        ]
    lines += [
        f"\tpartition '{name}' = entity",
        "\t\tmode: directLake",
        "\t\tsource",
        f"\t\t\tentityName: {name}",
        "\t\t\tschemaName: dbo",
        "\t\t\texpressionSource: DatabaseQuery",
        "",
    ]
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description="Create the ccg Direct Lake semantic model")
    parser.add_argument("--model-name", default="Claude Usage")
    parser.add_argument("--workspace", help="Workspace name (default: onelake sync config)")
    parser.add_argument("--lakehouse", help="Lakehouse name (default: onelake sync config)")
    parser.add_argument("--store-id", action="store_true",
                        help="Store the created model id as semantic_model_id in sync config")
    args = parser.parse_args()

    config = get_sync_config("onelake")
    workspace = args.workspace or config.get("workspace")
    lakehouse = args.lakehouse or config.get("lakehouse")
    if not workspace or not lakehouse:
        raise SystemExit("No workspace/lakehouse. Run: ccg sync setup --provider onelake")

    endpoint = json.loads(fab([
        "get", f"{workspace}.Workspace/{lakehouse}.Lakehouse",
        "-q", "properties.sqlEndpointProperties",
    ]))
    print(f"SQL endpoint: {endpoint['connectionString']}")

    with tempfile.TemporaryDirectory() as tmp:
        model_dir = Path(tmp) / f"{args.model_name}.SemanticModel"
        definition = model_dir / "definition"
        tables_dir = definition / "tables"
        tables_dir.mkdir(parents=True)

        (model_dir / ".platform").write_text(json.dumps({
            "$schema": "https://developer.microsoft.com/json-schemas/fabric/gitIntegration/platformProperties/2.0.0/schema.json",
            "metadata": {"type": "SemanticModel", "displayName": args.model_name},
            "config": {"version": "2.0", "logicalId": str(uuid.uuid4())},
        }, indent=2))
        (model_dir / "definition.pbism").write_text(json.dumps({
            "$schema": "https://developer.microsoft.com/json-schemas/fabric/item/semanticModel/definitionProperties/1.0.0/schema.json",
            "version": "4.0",
            "settings": {},
        }, indent=2))
        (definition / "database.tmdl").write_text(f"database '{uuid.uuid4()}'\n")
        (definition / "model.tmdl").write_text(
            f"model '{args.model_name}'\n"
            "\tculture: en-US\n"
            "\tdefaultPowerBIDataSourceVersion: powerBI_V3\n"
            "\tdiscourageImplicitMeasures\n\n"
            + "".join(f"ref table '{t}'\n" for t in TABLES)
        )
        (definition / "expressions.tmdl").write_text(
            "expression DatabaseQuery =\n"
            "\t\tlet\n"
            f"\t\t\tdatabase = Sql.Database(\"{endpoint['connectionString']}\", \"{endpoint['id']}\")\n"
            "\t\tin\n"
            "\t\t\tdatabase\n"
            f"\tlineageTag: {uuid.uuid4()}\n"
        )
        (definition / "relationships.tmdl").write_text("\n".join(
            f"relationship {uuid.uuid4()}\n\tfromColumn: {src}\n\ttoColumn: {dst}\n"
            for src, dst in RELATIONSHIPS
        ))
        for name in TABLES:
            (tables_dir / f"{name}.tmdl").write_text(table_tmdl(name))

        print(fab([
            "import", f"{workspace}.Workspace/{args.model_name}.SemanticModel",
            "-i", str(model_dir), "-f",
        ]))

    model_id = fab([
        "get", f"{workspace}.Workspace/{args.model_name}.SemanticModel", "-q", "id",
    ]).strip('"').strip()
    print(f"Model id: {model_id}")

    if args.store_id:
        config["semantic_model_id"] = model_id
        set_sync_config("onelake", config)
        print("Stored semantic_model_id in sync config")


if __name__ == "__main__":
    main()
