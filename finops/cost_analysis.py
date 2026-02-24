import pandas as pd
import os

CSV_PATH = os.path.join(os.path.dirname(__file__), "..", "aws_costs.csv")


def load_data():
    df = pd.read_csv(CSV_PATH, parse_dates=["date"])
    df["month"] = df["date"].dt.to_period("M")
    return df


def spend_by_service(df):
    print("\n" + "=" * 70)
    print("  1. TOTAL SPEND BY SERVICE & USAGE TYPE")
    print("=" * 70)

    agg = df.groupby(["service", "usage_type"])["amount"].sum().reset_index()
    agg = agg.sort_values("amount", ascending=False)
    total = agg["amount"].sum()
    agg["pct_of_total"] = (agg["amount"] / total * 100).round(1)

    for _, row in agg.iterrows():
        print(f"  {row['service']:<20s} {row['usage_type']:<30s} ${row['amount']:>8.2f}  ({row['pct_of_total']:>5.1f}%)")

    print(f"  {'':20s} {'TOTAL':<30s} ${total:>8.2f}  (100.0%)")
    return agg, total


def spend_by_env(df):
    print("\n" + "=" * 70)
    print("  2. SPEND BY ENVIRONMENT")
    print("=" * 70)

    env_agg = df.groupby("Env")["amount"].agg(["sum", "count"]).reset_index()
    env_agg.columns = ["Env", "total_spend", "line_items"]
    total = env_agg["total_spend"].sum()
    env_agg["pct"] = (env_agg["total_spend"] / total * 100).round(1)

    for _, row in env_agg.iterrows():
        print(f"  {row['Env']:<8s}  ${row['total_spend']:>8.2f}  ({row['pct']:>5.1f}%)  [{int(row['line_items'])} line items]")

    prod = env_agg[env_agg["Env"] == "prod"]["total_spend"].values[0]
    dev = env_agg[env_agg["Env"] == "dev"]["total_spend"].values[0]
    print(f"\n  Prod/Dev ratio: {prod / dev:.1f}x")
    return env_agg


def monthly_trend(df):
    print("\n" + "=" * 70)
    print("  3. MONTH-OVER-MONTH TREND")
    print("=" * 70)

    monthly = df.groupby("month")["amount"].sum().reset_index()
    monthly.columns = ["month", "total"]

    for _, row in monthly.iterrows():
        bar = "#" * int(row["total"] / 20)
        print(f"  {row['month']}  ${row['total']:>8.2f}  {bar}")

    if len(monthly) >= 2:
        jan = monthly.iloc[0]["total"]
        feb = monthly.iloc[1]["total"]
        delta = feb - jan
        pct = (delta / jan * 100)
        direction = "UP" if delta > 0 else "DOWN"
        print(f"\n  MoM change: {direction} ${abs(delta):.2f} ({pct:+.1f}%)")

    return monthly


def tag_audit(df):
    print("\n" + "=" * 70)
    print("  4. TAG COVERAGE AUDIT")
    print("=" * 70)

    tag_cols = ["App", "Env", "Owner", "CostCenter"]
    total_rows = len(df)

    for tag in tag_cols:
        present = df[tag].notna() & (df[tag].astype(str).str.strip() != "")
        coverage = present.sum()
        pct = coverage / total_rows * 100
        missing_rows = df[~present]
        status = "OK" if coverage == total_rows else "!!"

        print(f"  {status} {tag:<12s}  {coverage}/{total_rows} ({pct:.0f}%)", end="")
        if not missing_rows.empty:
            missing_desc = ", ".join(
                f"{r['service']}:{r['usage_type']}({r['Env']})"
                for _, r in missing_rows.iterrows()
            )
            print(f"  -- Missing on: {missing_desc}", end="")
        print()

    unattributable = df[
        (df["Owner"].isna() | (df["Owner"].astype(str).str.strip() == "")) |
        (df["CostCenter"].isna() | (df["CostCenter"].astype(str).str.strip() == ""))
    ]["amount"].sum()
    print(f"\n  Unattributable spend (missing Owner or CostCenter): ${unattributable:.2f}")


def savings_projections(df, total):
    print("\n" + "=" * 70)
    print("  5. SAVINGS PROJECTIONS (from raw data)")
    print("=" * 70)

    ec2_ondemand = df[df["usage_type"].str.startswith("BoxUsage")]["amount"].sum()
    ec2_spot = df[df["usage_type"].str.startswith("SpotUsage")]["amount"].sum()
    s3_total = df[df["service"] == "AmazonS3"]["amount"].sum()
    ebs_total = df[df["service"] == "EC2-Other"]["amount"].sum()

    print(f"\n  Category totals (computed from CSV):")
    print(f"    EC2 On-Demand:  ${ec2_ondemand:>8.2f}  ({ec2_ondemand/total*100:.1f}%)")
    print(f"    EC2 Spot:       ${ec2_spot:>8.2f}  ({ec2_spot/total*100:.1f}%)")
    print(f"    EBS:            ${ebs_total:>8.2f}  ({ebs_total/total*100:.1f}%)")
    print(f"    S3:             ${s3_total:>8.2f}  ({s3_total/total*100:.1f}%)")
    print(f"    Compute total:  ${ec2_ondemand + ebs_total:>8.2f}  ({(ec2_ondemand+ebs_total)/total*100:.1f}%)")

    spot_low = ec2_ondemand * 0.60
    spot_high = ec2_ondemand * 0.80
    print(f"\n  Savings #1 -- Spot Migration:")
    print(f"    Target spend:       ${ec2_ondemand:.2f}")
    print(f"    Spot discount:      60-80%")
    print(f"    Conservative (60%): ${spot_low:.2f} saved")
    print(f"    Aggressive  (80%): ${spot_high:.2f} saved")

    s3_storage = df[df["usage_type"].str.contains("Storage", case=False)]["amount"].sum()
    s3_requests = df[(df["service"] == "AmazonS3") & (df["usage_type"].str.contains("Requests", case=False))]["amount"].sum()
    lifecycle_low = s3_total * 0.40
    lifecycle_high = s3_total * 0.50
    print(f"\n  Savings #2 -- S3 Lifecycle Rules:")
    print(f"    S3 storage cost:    ${s3_storage:.2f}")
    print(f"    S3 request cost:    ${s3_requests:.2f}")
    print(f"    Total S3:           ${s3_total:.2f}")
    print(f"    Lifecycle savings:  40-50%")
    print(f"    Conservative (40%): ${lifecycle_low:.2f} saved")
    print(f"    Aggressive  (50%): ${lifecycle_high:.2f} saved")

    idle_low = ec2_ondemand * 0.10
    idle_high = ec2_ondemand * 0.20
    print(f"\n  Savings #3 -- Cluster Autotermination:")
    print(f"    Target spend:       ${ec2_ondemand:.2f}")
    print(f"    Est. idle %:        10-20%")
    print(f"    Conservative (10%): ${idle_low:.2f} saved")
    print(f"    Aggressive  (20%): ${idle_high:.2f} saved")

    combined_low = spot_low + lifecycle_low + idle_low
    combined_high = spot_high + lifecycle_high + idle_high
    new_low = total - combined_high
    new_high = total - combined_low
    print(f"\n  {'-' * 50}")
    print(f"  COMBINED SAVINGS SUMMARY:")
    print(f"    Current total spend:   ${total:.2f}/period")
    print(f"    Est. savings range:    ${combined_low:.2f} - ${combined_high:.2f}")
    print(f"    New projected spend:   ${new_low:.2f} - ${new_high:.2f}")
    print(f"    Overall reduction:     {combined_low/total*100:.0f}-{combined_high/total*100:.0f}%")


def main():
    print("+" + "=" * 70 + "+")
    print("|" + "  FinOps Quantitative Cost Analysis -- aws_costs.csv  ".center(70) + "|")
    print("+" + "=" * 70 + "+")

    df = load_data()
    print(f"\n  Loaded {len(df)} billing records from {df['date'].min().date()} to {df['date'].max().date()}")

    agg, total = spend_by_service(df)
    spend_by_env(df)
    monthly_trend(df)
    tag_audit(df)
    savings_projections(df, total)

    print(f"\n{'=' * 70}")
    print("  Analysis complete. All numbers computed directly from aws_costs.csv.")
    print(f"{'=' * 70}\n")


if __name__ == "__main__":
    main()
