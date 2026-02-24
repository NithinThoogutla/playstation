resource "aws_budgets_budget" "data_platform" {
  name              = "DataPlatform-Monthly-Budget"
  budget_type       = "COST"
  limit_amount      = var.budget_limit
  limit_unit        = "USD"
  time_unit         = "MONTHLY"

  notification {
    comparison_operator        = "GREATER_THAN"
    threshold                  = 80
    threshold_type             = "PERCENTAGE"
    notification_type          = "ACTUAL"
    subscriber_email_addresses = [var.budget_alert_email]
  }

  cost_filter {
    name = "TagKeyValue"
    values = [
      "user:App$DataPlatform"
    ]
  }
}
