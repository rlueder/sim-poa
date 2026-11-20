"""Linha de comando `sim-poa`."""

from __future__ import annotations

import argparse
import sys

from sim_poa.fetch import download, sources
from sim_poa.paths import DATA_DIR_ENV, raw_data_dir, repo_root


def _print_summary(summary: download.Summary) -> None:
    print()
    print(f"Baixados: {summary.downloaded} ({summary.bytes / 1e6:,.1f} MB)")
    print(f"Sem mudança: {summary.skipped}")
    if summary.adopted:
        print(f"Já presentes, registrados no manifesto: {summary.adopted}")
    sections = [
        ("Mudaram no servidor desde o manifesto", summary.changed),
        ("Fora do manifesto, ignorados em --frozen", summary.not_in_manifest),
        ("No manifesto, mas não estão mais no servidor", summary.gone_remote),
        ("Falhas", summary.failed),
    ]
    for title, items in sections:
        if items:
            print(f"{title}: {len(items)}")
            for item in items[:20]:
                print(f"  {item}")
            if len(items) > 20:
                print(f"  … e mais {len(items) - 20}")


def _fetch(args: argparse.Namespace) -> int:
    root = repo_root()
    config = sources.load(root / "data" / "sources.toml")
    if args.list:
        for s in config.sources:
            print(f"{s.group:12} {s.id:28} {s.kind:7} {s.description}")
        return 0
    try:
        selected = config.select(args.group or ["default"], args.source)
    except sources.SourceError as exc:
        print(f"sim-poa: {exc}", file=sys.stderr)
        return 2
    raw_dir = raw_data_dir()
    print(f"Dados brutos em {raw_dir} (altere com {DATA_DIR_ENV})")
    summary = download.run(
        config,
        selected,
        raw_dir,
        root / "data" / "manifest.csv",
        frozen=args.frozen,
        dry_run=args.dry_run,
    )
    _print_summary(summary)
    return 0 if summary.ok else 1


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="sim-poa")
    commands = parser.add_subparsers(dest="command", required=True)

    fetch = commands.add_parser("fetch", help="baixa os dados brutos de data/sources.toml")
    fetch.add_argument(
        "--group", action="append", help="grupo de fontes (padrão: default); repetível"
    )
    fetch.add_argument("--source", action="append", help="só esta fonte, pelo id; repetível")
    fetch.add_argument(
        "--frozen",
        action="store_true",
        help="reproduz o manifesto: falha se um arquivo mudou e ignora arquivos novos",
    )
    fetch.add_argument(
        "--dry-run", action="store_true", help="lista o que seria baixado, sem baixar"
    )
    fetch.add_argument("--list", action="store_true", help="lista as fontes e sai")
    fetch.set_defaults(handler=_fetch)
    return parser


def main(argv: list[str] | None = None) -> int:
    # Downloads longos costumam rodar com a saída redirecionada para um log;
    # sem isto, o Python acumula a saída e o log fica vazio por horas.
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(line_buffering=True)
    args = build_parser().parse_args(argv)
    handler = args.handler
    result: int = handler(args)
    return result


if __name__ == "__main__":
    sys.exit(main())
