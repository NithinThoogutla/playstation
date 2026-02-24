resource "aws_kms_key" "s3_key" {
  description             = "KMS key used to encrypt the data landing and curated buckets"
  deletion_window_in_days = 7
  enable_key_rotation     = true

  tags = {
    App        = "DataPlatform"
    Env        = var.environment
    Owner      = var.owner
    CostCenter = var.cost_center
  }
}

resource "aws_kms_alias" "s3_key_alias" {
  name          = "alias/data-platform-s3-key"
  target_key_id = aws_kms_key.s3_key.key_id
}

resource "aws_s3_bucket" "landing" {
  bucket        = "${var.bucket_prefix}-landing-${var.environment}"
  force_destroy = true

  tags = {
    App        = "DataPlatform"
    Env        = var.environment
    Owner      = var.owner
    CostCenter = var.cost_center
  }
}

resource "aws_s3_bucket" "curated" {
  bucket        = "${var.bucket_prefix}-curated-${var.environment}"
  force_destroy = true

  tags = {
    App        = "DataPlatform"
    Env        = var.environment
    Owner      = var.owner
    CostCenter = var.cost_center
  }
}

resource "aws_s3_bucket_public_access_block" "landing" {
  bucket                  = aws_s3_bucket.landing.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_public_access_block" "curated" {
  bucket                  = aws_s3_bucket.curated.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_server_side_encryption_configuration" "landing" {
  bucket = aws_s3_bucket.landing.id
  rule {
    apply_server_side_encryption_by_default {
      kms_master_key_id = aws_kms_key.s3_key.arn
      sse_algorithm     = "aws:kms"
    }
    bucket_key_enabled = true
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "curated" {
  bucket = aws_s3_bucket.curated.id
  rule {
    apply_server_side_encryption_by_default {
      kms_master_key_id = aws_kms_key.s3_key.arn
      sse_algorithm     = "aws:kms"
    }
    bucket_key_enabled = true
  }
}

data "aws_iam_policy_document" "landing_bucket_policy" {

  statement {
    sid       = "DenyInsecureTransport"
    effect    = "Deny"
    principals {
      type        = "AWS"
      identifiers = ["*"]
    }
    actions   = ["s3:*"]
    resources = [
      aws_s3_bucket.landing.arn,
      "${aws_s3_bucket.landing.arn}/*",
    ]
    condition {
      test     = "Bool"
      variable = "aws:SecureTransport"
      values   = ["false"]
    }
  }

  statement {
    sid       = "DenyNonKMSEncryptedUploads"
    effect    = "Deny"
    principals {
      type        = "AWS"
      identifiers = ["*"]
    }
    actions   = ["s3:PutObject"]
    resources = ["${aws_s3_bucket.landing.arn}/*"]
    condition {
      test     = "StringNotEquals"
      variable = "s3:x-amz-server-side-encryption"
      values   = ["aws:kms"]
    }
  }

  statement {
    sid       = "DenyPublicACLs"
    effect    = "Deny"
    principals {
      type        = "AWS"
      identifiers = ["*"]
    }
    actions = [
      "s3:PutBucketAcl",
      "s3:PutObjectAcl",
    ]
    resources = [
      aws_s3_bucket.landing.arn,
      "${aws_s3_bucket.landing.arn}/*",
    ]
    condition {
      test     = "StringEquals"
      variable = "s3:x-amz-acl"
      values   = ["public-read", "public-read-write"]
    }
  }
}

resource "aws_s3_bucket_policy" "landing" {
  bucket = aws_s3_bucket.landing.id
  policy = data.aws_iam_policy_document.landing_bucket_policy.json
}

data "aws_iam_policy_document" "curated_bucket_policy" {

  statement {
    sid       = "DenyInsecureTransport"
    effect    = "Deny"
    principals {
      type        = "AWS"
      identifiers = ["*"]
    }
    actions   = ["s3:*"]
    resources = [
      aws_s3_bucket.curated.arn,
      "${aws_s3_bucket.curated.arn}/*",
    ]
    condition {
      test     = "Bool"
      variable = "aws:SecureTransport"
      values   = ["false"]
    }
  }

  statement {
    sid       = "DenyNonKMSEncryptedUploads"
    effect    = "Deny"
    principals {
      type        = "AWS"
      identifiers = ["*"]
    }
    actions   = ["s3:PutObject"]
    resources = ["${aws_s3_bucket.curated.arn}/*"]
    condition {
      test     = "StringNotEquals"
      variable = "s3:x-amz-server-side-encryption"
      values   = ["aws:kms"]
    }
  }

  statement {
    sid       = "DenyPublicACLs"
    effect    = "Deny"
    principals {
      type        = "AWS"
      identifiers = ["*"]
    }
    actions = [
      "s3:PutBucketAcl",
      "s3:PutObjectAcl",
    ]
    resources = [
      aws_s3_bucket.curated.arn,
      "${aws_s3_bucket.curated.arn}/*",
    ]
    condition {
      test     = "StringEquals"
      variable = "s3:x-amz-acl"
      values   = ["public-read", "public-read-write"]
    }
  }
}

resource "aws_s3_bucket_policy" "curated" {
  bucket = aws_s3_bucket.curated.id
  policy = data.aws_iam_policy_document.curated_bucket_policy.json
}

resource "aws_s3_bucket_versioning" "curated" {
  bucket = aws_s3_bucket.curated.id
  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_lifecycle_configuration" "landing" {
  bucket = aws_s3_bucket.landing.id

  rule {
    id     = "transition-and-delete-raw-data"
    status = "Enabled"
    filter {}

    transition {
      days          = 7
      storage_class = "STANDARD_IA"
    }

    transition {
      days          = 30
      storage_class = "DEEP_ARCHIVE"
    }

    expiration {
      days = 90
    }
  }
}
