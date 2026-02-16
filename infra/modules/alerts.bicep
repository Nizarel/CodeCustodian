// Azure Monitor scheduled query alerts for CodeCustodian
param projectName string
param environment string
param location string
param appInsightsId string

var alertPrefix = '${projectName}-${environment}'

resource prSuccessRateAlert 'Microsoft.Insights/scheduledQueryRules@2023-12-01' = {
  name: '${alertPrefix}-pr-success-rate-low'
  location: location
  properties: {
    description: 'PR success rate below 90%'
    enabled: true
    severity: 2
    scopes: [
      appInsightsId
    ]
    evaluationFrequency: 'PT15M'
    windowSize: 'PT1H'
    criteria: {
      allOf: [
        {
          query: 'customMetrics | where name == "pr_success_rate" | summarize AggregatedValue=avg(value)'
          timeAggregation: 'Average'
          metricMeasureColumn: 'AggregatedValue'
          operator: 'LessThan'
          threshold: 90
          failingPeriods: {
            numberOfEvaluationPeriods: 1
            minFailingPeriodsToAlert: 1
          }
        }
      ]
    }
    autoMitigate: true
    targetResourceTypes: [
      'microsoft.insights/components'
    ]
  }
}

resource costBudgetAlert 'Microsoft.Insights/scheduledQueryRules@2023-12-01' = {
  name: '${alertPrefix}-budget-exceeded'
  location: location
  properties: {
    description: 'Budget utilization exceeds 100%'
    enabled: true
    severity: 2
    scopes: [
      appInsightsId
    ]
    evaluationFrequency: 'PT15M'
    windowSize: 'PT1H'
    criteria: {
      allOf: [
        {
          query: 'customMetrics | where name == "budget_utilization_pct" | summarize AggregatedValue=avg(value)'
          timeAggregation: 'Average'
          metricMeasureColumn: 'AggregatedValue'
          operator: 'GreaterThan'
          threshold: 100
          failingPeriods: {
            numberOfEvaluationPeriods: 1
            minFailingPeriodsToAlert: 1
          }
        }
      ]
    }
    autoMitigate: true
    targetResourceTypes: [
      'microsoft.insights/components'
    ]
  }
}

resource highSeveritySpikeAlert 'Microsoft.Insights/scheduledQueryRules@2023-12-01' = {
  name: '${alertPrefix}-high-severity-spike'
  location: location
  properties: {
    description: 'High-severity security finding spike detected'
    enabled: true
    severity: 1
    scopes: [
      appInsightsId
    ]
    evaluationFrequency: 'PT15M'
    windowSize: 'PT1H'
    criteria: {
      allOf: [
        {
          query: 'customMetrics | where name == "high_severity_findings" | summarize AggregatedValue=sum(value)'
          timeAggregation: 'Total'
          metricMeasureColumn: 'AggregatedValue'
          operator: 'GreaterThan'
          threshold: 10
          failingPeriods: {
            numberOfEvaluationPeriods: 1
            minFailingPeriodsToAlert: 1
          }
        }
      ]
    }
    autoMitigate: true
    targetResourceTypes: [
      'microsoft.insights/components'
    ]
  }
}

resource pipelineFailureRateAlert 'Microsoft.Insights/scheduledQueryRules@2023-12-01' = {
  name: '${alertPrefix}-pipeline-failure-rate-high'
  location: location
  properties: {
    description: 'Pipeline failure rate exceeds 10%'
    enabled: true
    severity: 2
    scopes: [
      appInsightsId
    ]
    evaluationFrequency: 'PT15M'
    windowSize: 'PT1H'
    criteria: {
      allOf: [
        {
          query: 'customMetrics | where name == "pipeline_failure_rate" | summarize AggregatedValue=avg(value)'
          timeAggregation: 'Average'
          metricMeasureColumn: 'AggregatedValue'
          operator: 'GreaterThan'
          threshold: 10
          failingPeriods: {
            numberOfEvaluationPeriods: 1
            minFailingPeriodsToAlert: 1
          }
        }
      ]
    }
    autoMitigate: true
    targetResourceTypes: [
      'microsoft.insights/components'
    ]
  }
}

output alertRuleIds array = [
  prSuccessRateAlert.id
  costBudgetAlert.id
  highSeveritySpikeAlert.id
  pipelineFailureRateAlert.id
]
