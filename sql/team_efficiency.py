from pyspark.sql import SparkSession
from pyspark.sql.functions import col, sum as _sum, round as _round, expr

def create_spark_session():
    return SparkSession.builder \
        .appName("TeamEfficiencyETL") \
        .getOrCreate()

def main():
    spark = create_spark_session()

    batting_df = spark.read.csv("../data/landing/Batting.csv", header=True, inferSchema=True)
    salaries_df = spark.read.csv("../data/landing/Salaries.csv", header=True, inferSchema=True)

    batting_df = batting_df.filter(col("yearID").isNotNull() & col("teamID").isNotNull())
    salaries_df = salaries_df.filter(col("yearID").isNotNull() & col("teamID").isNotNull())

    team_batting = batting_df.groupBy("yearID", "teamID").agg(
        _sum("AB").alias("total_AB"),
        _sum("H").alias("total_H"),
        _sum("HR").alias("total_HR"),
        _sum(expr("H + 2B + 2 * 3B + 3 * HR")).alias("total_bases")
    )

    team_batting = team_batting.withColumn(
        "BA",
        _round(expr("CASE WHEN total_AB = 0 THEN NULL ELSE total_H / total_AB END"), 3)
    ).withColumn(
        "SLG",
        _round(expr("CASE WHEN total_AB = 0 THEN NULL ELSE total_bases / total_AB END"), 3)
    )

    team_salaries = salaries_df.groupBy("yearID", "teamID").agg(
        _sum("salary").alias("total_payroll")
    )

    efficiency_df = team_batting.alias("b").join(
        team_salaries.alias("s"),
        on=["yearID", "teamID"],
        how="left"
    )

    efficiency_df = efficiency_df.withColumn(
        "HR_per_Million",
        _round(expr("CASE WHEN total_payroll IS NULL OR total_payroll = 0 THEN NULL ELSE total_HR / (total_payroll / 1000000.0) END"), 2)
    )

    final_output = efficiency_df.select(
        "teamID", "yearID", "total_payroll",
        col("total_AB").alias("AB"),
        col("total_HR").alias("HR"),
        "BA", "SLG", "HR_per_Million"
    ).filter(col("total_payroll").isNotNull()) \
     .orderBy(col("yearID").desc(), col("teamID").asc())

    final_output.show(15, truncate=False)

    spark.stop()

if __name__ == "__main__":
    main()
