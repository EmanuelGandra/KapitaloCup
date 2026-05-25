from pathlib import Path

import pandas as pd

from src.db import get_supabase


def clean_record(record: dict) -> dict:
    cleaned = {}

    for key, value in record.items():
        if pd.isna(value):
            cleaned[key] = None
        else:
            cleaned[key] = value

    return cleaned


def main():
    supabase = get_supabase()

    csv_path = Path("data/wc2026_group_stage_seed.csv")
    df = pd.read_csv(csv_path)

    for rec in df.to_dict(orient="records"):
        rec = clean_record(rec)
        supabase.table("matches").upsert(rec, on_conflict="match_id").execute()

    print(f"Seed concluído: {len(df)} jogos inseridos/atualizados na tabela matches.")


if __name__ == "__main__":
    main()