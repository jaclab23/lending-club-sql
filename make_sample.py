import csv, random, pathlib
random.seed(42)
src = pathlib.Path(r"..\lending-club\LC_loans_granting_model_dataset.csv")
dst = pathlib.Path("sample/loans_sample.csv")
dst.parent.mkdir(exist_ok=True)
TARGET = 100_000

with src.open(newline="", encoding="utf-8") as f:
    reader = csv.reader(f)
    header = next(reader)
    # Reservoir sample: one pass, bounded memory, deterministic under the seed.
    reservoir = []
    for i, row in enumerate(reader):
        if i < TARGET:
            reservoir.append(row)
        else:
            j = random.randint(0, i)
            if j < TARGET:
                reservoir[j] = row

with dst.open("w", newline="", encoding="utf-8") as f:
    w = csv.writer(f)
    w.writerow(header)
    w.writerows(reservoir)

print(f"wrote {dst} | {len(reservoir):,} rows | {dst.stat().st_size/1e6:.1f} MB")
