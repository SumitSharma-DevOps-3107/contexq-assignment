"""Reproducible fixtures: 2,400 source rows describing 1,800 companies."""
import argparse
import csv
import random
from pathlib import Path


def generate(directory: Path) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    for source, start, suffix in [("supply", 0, "Ltd"), ("financial", 600, "Limited")]:
        rows = []
        for i in range(start, start + 1200):
            rng = random.Random(i)
            employees = rng.randint(10, 5000)
            age = rng.randint(1, 80)
            assets = employees * rng.uniform(40000, 150000)
            revenue = employees * 120000 + assets * 0.3 + age * 20000
            revenue *= rng.uniform(0.9, 1.1)
            rows.append(dict(source=source, corporate_name=f"Company {i:05d} {suffix}",
                             registration_id=f"REG-{i:06d}", country="IN",
                             employees=employees, company_age=age,
                             assets_usd=round(assets, 2), annual_revenue_usd=round(revenue, 2)))
        with (directory / f"{source}.csv").open("w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=rows[0].keys())
            writer.writeheader()
            writer.writerows(rows)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=Path("data"))
    generate(parser.parse_args().output)
