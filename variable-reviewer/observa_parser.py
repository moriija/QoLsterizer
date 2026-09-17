#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import argparse
import csv
import json
import os
import re
import statistics
import sys
from collections import defaultdict, Counter

COLUMN_HINTS = {
    "nome": ["nome", "variavel", "variável", "indicador"],
    "regiao": ["regi"],
    "periodo": ["per"],
    "resultado": ["result", "valor"],
}


def normalize(s):
    return s.strip().lower()


def detect_columns(header):
    norm = [normalize(h) for h in header]
    mapping = {}
    for logical, hints in COLUMN_HINTS.items():
        found = None
        for idx, col in enumerate(norm):
            if any(hint in col for hint in hints):
                found = idx
                break
        if found is None:
            raise ValueError(
                f"Não encontrei uma coluna para '{logical}' no cabeçalho {header}. "
                f"Esperado algo como Nome;Região;Período;Resultado."
            )
        mapping[logical] = found
    return mapping


def sniff_delimiter(sample_line):
    if sample_line.count(";") >= sample_line.count(","):
        return ";"
    return ","


def load_rows(path):
    with open(path, "r", encoding="utf-8-sig", newline="") as fh:
        first_line = fh.readline()
        delimiter = sniff_delimiter(first_line)
        fh.seek(0)
        reader = csv.reader(fh, delimiter=delimiter)
        header = next(reader)
        colmap = detect_columns(header)

        rows = []
        skipped = 0
        for raw in reader:
            if not raw or all(not c.strip() for c in raw):
                continue
            try:
                nome = raw[colmap["nome"]].strip()
                regiao = raw[colmap["regiao"]].strip()
                periodo_raw = raw[colmap["periodo"]].strip()
                resultado = raw[colmap["resultado"]].strip()
            except IndexError:
                skipped += 1
                continue

            m = re.search(r"-?\d+", periodo_raw)
            if not m:
                skipped += 1
                continue
            periodo = int(m.group())

            rows.append((nome, regiao, periodo, resultado))
        if skipped:
            print(f"  (aviso: {skipped} linha(s) de {os.path.basename(path)} ignorada(s) — período inválido)")
        return rows


def region_type(regiao):
    m = re.search(r"\(([^)]+)\)\s*$", regiao)
    return m.group(1) if m else "Outro"


def format_year_ranges(years):
    years = sorted(set(years))
    if not years:
        return "sem dados"
    ranges = []
    start = prev = years[0]
    for y in years[1:]:
        if y == prev + 1:
            prev = y
            continue
        ranges.append((start, prev))
        start = prev = y
    ranges.append((start, prev))
    parts = [f"{a}-{b}" if a != b else f"{a}" for a, b in ranges]
    return ", ".join(parts)


def print_report(rows):
    print("=" * 78)
    print("RELATÓRIO")
    print("=" * 78)
    variables = sorted(set(r[0] for r in rows))
    regions = sorted(set(r[1] for r in rows))
    print(f"Total de linhas (registros):     {len(rows)}")
    print(f"Total de variáveis distintas:     {len(variables)}")
    print(f"Total de regiões distintas:       {len(regions)}")
    print()

    periods = [r[2] for r in rows]
    try:
        moda = statistics.mode(periods)
    except statistics.StatisticsError:
        moda = ", ".join(str(m) for m in statistics.multimode(periods))
    media = statistics.mean(periods)
    mediana = statistics.median(periods)

    print("Estatísticas do intervalo de datas ('Período'), considerando todas as linhas:")
    print(f"  Moda:    {moda}")
    print(f"  Média:   {media:.2f}")
    print(f"  Mediana: {mediana}")
    print(f"  (intervalo total observado: {min(periods)}-{max(periods)})")
    print()

    counts = Counter(r[1] for r in rows)
    by_type = defaultdict(list)
    for regiao, cnt in counts.items():
        by_type[region_type(regiao)].append((regiao, cnt))

    print("Quantidade de registros por Distrito/Subprefeitura/Município:")
    for tipo in sorted(by_type):
        print(f"  -- {tipo} --")
        for regiao, cnt in sorted(by_type[tipo]):
            print(f"     {regiao}: {cnt} registro(s)")
    print("=" * 78)
    print()


def build_json(rows, sources):
    variables = sorted(set(r[0] for r in rows))
    regions = sorted(set(r[1] for r in rows))
    periods = [r[2] for r in rows]

    try:
        moda_list = statistics.multimode(periods)
    except Exception:
        moda_list = [periods[0]]

    region_counts = Counter(r[1] for r in rows)

    grouped = defaultdict(lambda: defaultdict(list))
    for nome, regiao, periodo, resultado in rows:
        grouped[nome][regiao].append([periodo, resultado])
    for nome in grouped:
        for regiao in grouped[nome]:
            grouped[nome][regiao].sort(key=lambda t: t[0])

    variables_json = []
    for nome in variables:
        region_data = grouped[nome]
        years = [p for vals in region_data.values() for p, _ in vals]
        variables_json.append({
            "nome": nome,
            "yearRange": format_year_ranges(years),
            "regions": region_data,
        })

    return {
        "meta": {
            "sources": sources,
            "totalRows": len(rows),
            "totalVariables": len(variables),
            "totalRegions": len(regions),
            "periodStats": {
                "moda": moda_list,
                "media": round(statistics.mean(periods), 2),
                "mediana": statistics.median(periods),
                "min": min(periods),
                "max": max(periods),
            },
            "regionCounts": dict(region_counts),
        },
        "variables": variables_json,
    }


def main():
    parser = argparse.ArgumentParser(description="Parser de CSVs no formato ObservaSampa -> JSON para observa_review.html")
    parser.add_argument("input_csvs", nargs="+", help="Um ou mais arquivos CSV (Nome;Região;Período;Resultado)")
    parser.add_argument("-o", "--output", default="dataset.json", help="Arquivo JSON de saída (padrão: dataset.json)")
    args = parser.parse_args()

    all_rows = []
    sources = []
    for path in args.input_csvs:
        if not os.path.exists(path):
            print(f"Arquivo não encontrado: {path}")
            sys.exit(1)
        print(f"Lendo {path} ...")
        rows = load_rows(path)
        print(f"  {len(rows)} linha(s) carregada(s).")
        all_rows.extend(rows)
        sources.append(os.path.basename(path))

    print()
    print_report(all_rows)

    data = build_json(all_rows, sources)
    with open(args.output, "w", encoding="utf-8") as fh:
        json.dump(data, fh, ensure_ascii=False, separators=(",", ":"))

    size_mb = os.path.getsize(args.output) / (1024 * 1024)
    print(f"JSON gerado: {args.output} ({size_mb:.1f} MB)")
    print("Abra observa_review.html e carregue esse arquivo para revisar as variáveis.")


if __name__ == "__main__":
    main()
