# Data Platform Take-Home Assignment

This is my submission for the Data Engineering take-home assignment. Since I don't have a personal AWS or Databricks sandbox, I built the repo so it can be tested fully locally. The infrastructure is defined in Terraform and ready to deploy, but the pipeline itself can be run on any machine with Python installed.

## Repository Layout

```text
├── data/
│   ├── landing/
│   └── curated/
├── infra/
│   ├── s3.tf
│   ├── iam.tf
│   ├── governance.tf
│   ├── provider.tf
│   └── variables.tf
├── pipelines/
│   ├── cluster_policy.json
│   ├── pool_config.json
│   ├── job.json
│   └── ingestion.py
├── sql/
│   ├── team_efficiency.py
│   ├── team_efficiency.sql
│   └── sample_output.txt
├── finops/
│   └── finops_cost_analysis.md
└── docs/
    └── README.md
```

## Architecture and Security

For storage I separated the landing and curated zones into two distinct S3 buckets. I did this mainly to keep the IAM boundaries clean and limit the blast radius in case something goes wrong.

**Bucket-level security enforcement:**
- **Block Public Access** — all four BPA settings enabled on both buckets.
- **TLS enforcement** — explicit `Deny` on `s3:*` when `aws:SecureTransport = false`.
- **KMS-only uploads** — explicit `Deny` on `s3:PutObject` when `s3:x-amz-server-side-encryption != aws:kms`.
- **Public ACL denial** — explicit `Deny` on `PutBucketAcl` / `PutObjectAcl` when `s3:x-amz-acl` is `public-read` or `public-read-write`.

The IAM role for Databricks is tightly scoped:
- **Landing bucket** — `GetObject` + `ListBucket` only (read). An explicit `Deny` prevents any `PutObject` / `DeleteObject` against landing.
- **Curated bucket** — `GetObject` + `ListBucket` for reads, `PutObject` + `DeleteObject` for writes.
- **KMS** — only `Decrypt`, `GenerateDataKey`, and `DescribeKey` on the single data-platform key.

For cost control I set up several layers:
1. **S3 lifecycle rules** — raw landing data transitions Standard → Standard-IA (7 days) → Glacier Deep Archive (30 days) → deleted at 90 days.
2. **Cluster policy** — 15-minute autotermination, job-only clusters, capped at 8 workers, pool required, LTS runtime enforced.
3. **Instance pool** — Spot with On-Demand fallback, 60% bid price, 10-minute idle termination.
4. **Budget alert** — AWS Budget scoped to `App:DataPlatform` tag, alert at 80% of monthly threshold.

## Idempotency & Determinism

Every part of this pipeline is designed to be safely re-runnable, producing identical output regardless of how many times it executes.

**Ingestion pipeline (`ingestion.py`):**
- All writes use `mode("overwrite")`, which means each run completely replaces the curated output. If a job fails halfway through and retries, the second run clobbers any partial output from the first. There's no append-only logic, no auto-incrementing IDs, and no wall-clock timestamps embedded in the data — so two runs against the same landing data always produce byte-identical curated tables.
- Partitioned writes (`partitionBy("yearID")`) are deterministic because Spark partitioning is based solely on column values, not on execution order or timing.

**SQL aggregation (`team_efficiency.py` / `team_efficiency.sql`):**
- Grouping by `yearID` and `teamID` before joining eliminates double-counting for players with multiple stints. The left join ensures teams with missing salary data aren't dropped. Running this query N times against the same curated data always returns the same result set.

**Terraform (`infra/`):**
- Terraform's declarative model is inherently idempotent — `terraform plan` shows a diff, and `terraform apply` converges the infrastructure to the declared state. Re-applying the same config is a no-op. Resources use `create_before_destroy` lifecycle semantics where applicable.

**Job retries (`job.json`):**
- The Databricks job is configured with `max_retries: 2` and a 5-minute backoff (`min_retry_interval_millis: 300000`). Because the pipeline is idempotent, retries are safe — they just re-process the same data and overwrite the same output.

## Data Quality Strategy

The ingestion pipeline applies a layered DQ validation on every table before writing to curated. Here's the full chain:

| Check | What it does | Example |
|---|---|---|
| **Schema assertion** | Verifies min expected column count per table | Batting must have ≥ 22 columns |
| **Null-key rejection** | Drops rows where primary/foreign keys are null | `playerID`, `yearID`, `teamID` |
| **Range validation** | Drops rows with out-of-bounds numeric values | `yearID` ∈ [1800, 2100], `salary > 0`, `AB ≥ 0` |
| **Deduplication** | Drops exact-key duplicates (keeps first) | `(playerID, yearID, stint)` for Batting |
| **DQ metrics logging** | Prints rows read, rows dropped, and pass rate | Visible in Databricks job logs |

This gives us lightweight observability without a separate metrics service — the Databricks job logs themselves become the DQ audit trail.

## Prerequisites

- Python 3.10+ with `pyspark`, `pandas`, and `boto3` installed
- Terraform 1.5+
- An AWS account (only needed for actual deployment)
- Databricks CLI / Workspace (optional)

## Setting Up Credentials

I didn't hardcode any credentials anywhere in the codebase. To authenticate locally, copy the env template, fill in your values, and source it:

```bash
cp .env.example .env
# open .env and add your AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY, and Databricks endpoint
source .env
```

Terraform picks up the AWS environment variables automatically during `terraform plan`. The `.env` file is listed in `.gitignore` so it won't get committed by accident.

## Running Locally

**Terraform validation**
```bash
cd infra/
terraform init
terraform validate
terraform plan -out=tfplan
```

**PySpark ingestion**
```bash
cd pipelines/
pip install pyspark
python3 ingestion.py
```

After running this you should see the partitioned Parquet folders generated under `/data/curated/`.

**Analytical aggregation**
```bash
cd sql/
python3 team_efficiency.py
```

**FinOps quantitative analysis**
```bash
cd finops/
python3 cost_analysis.py
```

This script processes `aws_costs.csv` and produces spend breakdowns by service, environment, month-over-month trends, tag coverage audit, and savings projections with dollar estimates.

## CI/CD Integration

The infrastructure is designed to be deployed through a GitHub Actions pipeline. Here's how I'd wire it up:

**Workflow strategy:**
- `terraform plan` runs automatically on every pull request to any `infra/**` file.
- `terraform apply` runs only on merge to `main`, gated behind a manual approval step for `prod`.
- A workspace matrix (`dev`, `staging`, `prod`) ensures each environment gets its own plan/apply cycle with isolated state files.

**Authentication:**
- AWS authentication uses OIDC federation (the `cicd_role` in `iam.tf` is already configured for this). No long-lived IAM keys are stored in GitHub — the workflow assumes the role via `aws-actions/configure-aws-credentials` with the OIDC token.

**Sample workflow:**

```yaml
name: Terraform CI/CD

on:
  pull_request:
    paths: ['infra/**']
  push:
    branches: [main]
    paths: ['infra/**']

permissions:
  id-token: write
  contents: read

jobs:
  plan:
    runs-on: ubuntu-latest
    strategy:
      matrix:
        workspace: [dev, staging, prod]
    steps:
      - uses: actions/checkout@v4
      - uses: aws-actions/configure-aws-credentials@v4
        with:
          role-to-assume: arn:aws:iam::233096558879:role/terraform-cicd-role-${{ matrix.workspace }}
          aws-region: us-east-1
      - uses: hashicorp/setup-terraform@v3
      - run: terraform init -backend-config="key=${{ matrix.workspace }}/terraform.tfstate"
        working-directory: infra
      - run: terraform workspace select -or-create ${{ matrix.workspace }}
        working-directory: infra
      - run: terraform plan -var="environment=${{ matrix.workspace }}" -out=tfplan
        working-directory: infra

  apply:
    if: github.ref == 'refs/heads/main' && github.event_name == 'push'
    needs: plan
    runs-on: ubuntu-latest
    strategy:
      matrix:
        workspace: [dev, staging, prod]
    environment: ${{ matrix.workspace }}   # requires manual approval for prod
    steps:
      - uses: actions/checkout@v4
      - uses: aws-actions/configure-aws-credentials@v4
        with:
          role-to-assume: arn:aws:iam::233096558879:role/terraform-cicd-role-${{ matrix.workspace }}
          aws-region: us-east-1
      - uses: hashicorp/setup-terraform@v3
      - run: terraform init -backend-config="key=${{ matrix.workspace }}/terraform.tfstate"
        working-directory: infra
      - run: terraform workspace select ${{ matrix.workspace }}
        working-directory: infra
      - run: terraform apply -auto-approve -var="environment=${{ matrix.workspace }}"
        working-directory: infra
```

The `prod` environment in GitHub is configured with a required reviewer, so apply won't execute until a team member approves the plan output.

## Governance and Access Control

For access control I would define external locations for both S3 buckets in Unity Catalog and structure the catalog as `sports_analytics_catalog` with `raw` and `curated` schemas. Table grants would be tied to AD or Okta groups rather than individual users.

For secrets I would use AWS Secrets Manager as the backend, surface them in Databricks through a Secret Scope, and reference them in jobs using `dbutils.secrets.get()`.
