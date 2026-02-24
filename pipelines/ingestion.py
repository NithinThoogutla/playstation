from pyspark.sql import SparkSession
from pyspark.sql import DataFrame
from pyspark.sql.functions import col
import argparse
import sys

EXPECTED_MIN_COLUMNS = {
    "Batting":        22,
    "Salaries":        5,
    "People":         24,
    "Schools":         5,
    "CollegePlaying":  3,
}

REQUIRED_NOT_NULL = {
    "Batting":        ["playerID", "yearID", "teamID"],
    "Salaries":       ["playerID", "yearID", "teamID"],
    "People":         ["playerID"],
    "Schools":        ["schoolID"],
    "CollegePlaying": ["playerID", "schoolID", "yearID"],
}

RANGE_RULES = {
    "yearID":  (1800, 2100),
    "salary":  (1, None),
    "AB":      (0, None),
    "H":       (0, None),
    "HR":      (0, None),
}

DEDUP_KEYS = {
    "Batting":        ["playerID", "yearID", "stint"],
    "Salaries":       ["playerID", "yearID", "teamID"],
    "People":         ["playerID"],
    "Schools":        ["schoolID"],
    "CollegePlaying": ["playerID", "schoolID", "yearID"],
}


def create_spark_session():
    return SparkSession.builder \
        .appName("SportsAnalyticsIngestion") \
        .config("spark.jars.packages", "org.apache.hadoop:hadoop-aws:3.3.2,com.amazonaws:aws-java-sdk-bundle:1.11.1026") \
        .config("spark.hadoop.fs.s3a.impl", "org.apache.hadoop.fs.s3a.S3AFileSystem") \
        .config("spark.hadoop.fs.s3a.aws.credentials.provider", "com.amazonaws.auth.EnvironmentVariableCredentialsProvider") \
        .config("spark.hadoop.fs.s3a.connection.timeout", "60000") \
        .config("spark.hadoop.fs.s3a.connection.establish.timeout", "5000") \
        .getOrCreate()


def validate_dataframe(df: DataFrame, table_name: str) -> DataFrame:
    total_rows = df.count()
    print(f"  [DQ] Starting validation for {table_name} -- {total_rows} rows read")

    min_cols = EXPECTED_MIN_COLUMNS.get(table_name)
    if min_cols and len(df.columns) < min_cols:
        raise ValueError(
            f"Schema drift detected for {table_name}: "
            f"expected >= {min_cols} columns, got {len(df.columns)}"
        )
    print(f"  [DQ] Schema check passed ({len(df.columns)} columns)")

    not_null_cols = REQUIRED_NOT_NULL.get(table_name, [])
    for c in not_null_cols:
        if c in df.columns:
            before = df.count()
            df = df.filter(col(c).isNotNull())
            dropped = before - df.count()
            if dropped > 0:
                print(f"  [DQ] Dropped {dropped} rows with null '{c}'")

    for c, (lo, hi) in RANGE_RULES.items():
        if c in df.columns:
            before = df.count()
            if lo is not None:
                df = df.filter(col(c) >= lo)
            if hi is not None:
                df = df.filter(col(c) <= hi)
            dropped = before - df.count()
            if dropped > 0:
                print(f"  [DQ] Dropped {dropped} rows where '{c}' was out of range [{lo}, {hi}]")

    dedup_cols = DEDUP_KEYS.get(table_name, [])
    valid_dedup_cols = [c for c in dedup_cols if c in df.columns]
    if valid_dedup_cols:
        before = df.count()
        df = df.dropDuplicates(valid_dedup_cols)
        dropped = before - df.count()
        if dropped > 0:
            print(f"  [DQ] Dropped {dropped} duplicate rows on keys {valid_dedup_cols}")

    clean_rows = df.count()
    dropped_total = total_rows - clean_rows
    pass_rate = (clean_rows / total_rows * 100) if total_rows > 0 else 0.0
    print(f"  [DQ] Validation complete: {clean_rows}/{total_rows} rows passed ({pass_rate:.1f}%), {dropped_total} dropped")

    return df


def ingest_table(spark, table_name, landing_path, curated_path, partition_col=None):
    print(f"\n{'='*60}")
    print(f"  Processing: {table_name}")
    print(f"{'='*60}")
    source_uri = f"{landing_path}/{table_name}.csv"
    dest_uri = f"{curated_path}/{table_name}"

    try:
        df = spark.read.csv(source_uri, header=True, inferSchema=True)
        df = validate_dataframe(df, table_name)

        writer = df.write.mode("overwrite").format("parquet")

        if partition_col and partition_col in df.columns:
            writer = writer.partitionBy(partition_col)

        writer.save(dest_uri)
        print(f"  Done -- wrote clean {table_name} to {dest_uri}")

    except Exception as e:
        print(f"  FAILED processing {table_name}: {e}")
        sys.exit(1)


def main():
    parser = argparse.ArgumentParser(description="Ingest Baseball Data")
    parser.add_argument("--env", type=str, default="local", help="Environment (local, dev, prod)")
    parser.add_argument("--landing_prefix", type=str, default="../data/landing", help="Path to landing directory")
    parser.add_argument("--curated_prefix", type=str, default="../data/curated", help="Path to curated directory")

    args, unknown = parser.parse_known_args()

    spark = create_spark_session()

    configurations = [
        {"name": "Batting", "partition": "yearID"},
        {"name": "Salaries", "partition": "yearID"},
        {"name": "People", "partition": None},
        {"name": "Schools", "partition": None},
        {"name": "CollegePlaying", "partition": "yearID"}
    ]

    for config in configurations:
        ingest_table(
            spark,
            config["name"],
            args.landing_prefix,
            args.curated_prefix,
            config["partition"]
        )

    print(f"\n{'='*60}")
    print("  All tables ingested successfully.")
    print(f"{'='*60}")
    spark.stop()

if __name__ == "__main__":
    main()
