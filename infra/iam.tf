resource "aws_iam_role" "databricks_job_role" {
  name = "databricks-job-execution-role-${var.environment}"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "ec2.amazonaws.com"
        }
      }
    ]
  })
}

data "aws_iam_policy_document" "databricks_s3_access" {

  statement {
    sid    = "ListLandingBucket"
    effect = "Allow"
    actions = [
      "s3:ListBucket"
    ]
    resources = [
      aws_s3_bucket.landing.arn
    ]
    condition {
      test     = "StringLike"
      variable = "s3:prefix"
      values   = ["*"]
    }
  }

  statement {
    sid    = "ReadLandingObjects"
    effect = "Allow"
    actions = [
      "s3:GetObject"
    ]
    resources = [
      "${aws_s3_bucket.landing.arn}/*"
    ]
  }

  statement {
    sid    = "ListCuratedBucket"
    effect = "Allow"
    actions = [
      "s3:ListBucket"
    ]
    resources = [
      aws_s3_bucket.curated.arn
    ]
    condition {
      test     = "StringLike"
      variable = "s3:prefix"
      values   = ["*"]
    }
  }

  statement {
    sid    = "ReadCuratedObjects"
    effect = "Allow"
    actions = [
      "s3:GetObject"
    ]
    resources = [
      "${aws_s3_bucket.curated.arn}/*"
    ]
  }

  statement {
    sid    = "WriteCuratedObjects"
    effect = "Allow"
    actions = [
      "s3:PutObject",
      "s3:DeleteObject"
    ]
    resources = [
      "${aws_s3_bucket.curated.arn}/*"
    ]
  }

  statement {
    sid    = "DenyWriteToLanding"
    effect = "Deny"
    actions = [
      "s3:PutObject",
      "s3:DeleteObject"
    ]
    resources = [
      "${aws_s3_bucket.landing.arn}/*"
    ]
  }

  statement {
    sid    = "KMSEncryptDecrypt"
    effect = "Allow"
    actions = [
      "kms:Decrypt",
      "kms:GenerateDataKey",
      "kms:DescribeKey"
    ]
    resources = [aws_kms_key.s3_key.arn]
  }
}

resource "aws_iam_role_policy" "databricks_job_policy" {
  name   = "databricks-s3-rw-policy"
  role   = aws_iam_role.databricks_job_role.id
  policy = data.aws_iam_policy_document.databricks_s3_access.json
}

resource "aws_iam_instance_profile" "databricks" {
  name = "databricks-job-profile-${var.environment}"
  role = aws_iam_role.databricks_job_role.name
}

resource "aws_iam_role" "cicd_role" {
  name = "terraform-cicd-role-${var.environment}"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRoleWithWebIdentity"
        Effect = "Allow"
        Principal = {
          Federated = "arn:aws:iam::233096558879:oidc-provider/token.actions.githubusercontent.com"
        }
        Condition = {
          StringEquals = {
            "token.actions.githubusercontent.com:aud" : "sts.amazonaws.com"
          },
          StringLike = {
            "token.actions.githubusercontent.com:sub" : "repo:gopalakrishnachennu/Nitin-Project:*"
          }
        }
      }
    ]
  })
}

resource "aws_iam_role_policy_attachment" "cicd_policy" {
  role       = aws_iam_role.cicd_role.name
  policy_arn = "arn:aws:iam::aws:policy/PowerUserAccess"
}
