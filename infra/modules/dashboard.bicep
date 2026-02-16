// Azure Portal Dashboard for CodeCustodian observability
param projectName string
param environment string
param location string
param appInsightsId string
param lawId string

var dashboardName = '${projectName}-${environment}-dashboard'

resource dashboard 'Microsoft.Portal/dashboards@2022-12-01-preview' = {
  name: dashboardName
  location: location
  properties: any({
    lenses: [
      {
        order: 0
        parts: [
          {
            position: {
              x: 0
              y: 0
              rowSpan: 3
              colSpan: 6
            }
            metadata: {
              type: 'Extension/HubsExtension/PartType/MarkdownPart'
              settings: {
                content: {
                  content: '# Findings Over Time\n\nKQL:\n```kusto\ncustomMetrics\n| where name == "findings_count"\n| summarize Findings=sum(value) by bin(timestamp, 1d), tostring(customDimensions.type)\n```'
                }
              }
            }
          }
          {
            position: {
              x: 6
              y: 0
              rowSpan: 3
              colSpan: 6
            }
            metadata: {
              type: 'Extension/HubsExtension/PartType/MarkdownPart'
              settings: {
                content: {
                  content: '# PR Success Rate\n\nTarget: 95%+\n\nKQL:\n```kusto\ncustomMetrics\n| where name == "pr_success_rate"\n| summarize SuccessRate=avg(value) by bin(timestamp, 1d)\n```'
                }
              }
            }
          }
          {
            position: {
              x: 0
              y: 3
              rowSpan: 3
              colSpan: 6
            }
            metadata: {
              type: 'Extension/HubsExtension/PartType/MarkdownPart'
              settings: {
                content: {
                  content: '# Cost Savings\n\nKQL:\n```kusto\ncustomMetrics\n| where name in ("cost_savings_weekly", "cost_savings_cumulative")\n| summarize Amount=sum(value) by name, bin(timestamp, 1w)\n```'
                }
              }
            }
          }
          {
            position: {
              x: 6
              y: 3
              rowSpan: 3
              colSpan: 6
            }
            metadata: {
              type: 'Extension/HubsExtension/PartType/MarkdownPart'
              settings: {
                content: {
                  content: '# Confidence Distribution\n\nKQL:\n```kusto\ncustomMetrics\n| where name == "confidence_score"\n| summarize Count=count() by Score=bin(value, 1.0)\n```'
                }
              }
            }
          }
          {
            position: {
              x: 0
              y: 6
              rowSpan: 3
              colSpan: 6
            }
            metadata: {
              type: 'Extension/HubsExtension/PartType/MarkdownPart'
              settings: {
                content: {
                  content: '# Verification Pass Rate + MTTR\n\nKQL:\n```kusto\ncustomMetrics\n| where name in ("verification_pass_rate", "mttr_minutes")\n| summarize AvgValue=avg(value) by name, bin(timestamp, 1d)\n```'
                }
              }
            }
          }
          {
            position: {
              x: 6
              y: 6
              rowSpan: 3
              colSpan: 6
            }
            metadata: {
              type: 'Extension/HubsExtension/PartType/MarkdownPart'
              settings: {
                content: {
                  content: '# ROI Metrics\n\nKQL:\n```kusto\ncustomMetrics\n| where name in ("hours_saved", "cost_per_pr", "payback_days")\n| summarize AvgValue=avg(value) by name, bin(timestamp, 1w)\n```'
                }
              }
            }
          }
          {
            position: {
              x: 0
              y: 9
              rowSpan: 3
              colSpan: 6
            }
            metadata: {
              type: 'Extension/HubsExtension/PartType/MarkdownPart'
              settings: {
                content: {
                  content: '# Budget Utilization by Team\n\nKQL:\n```kusto\ncustomMetrics\n| where name == "budget_utilization_pct"\n| summarize Utilization=avg(value) by tostring(customDimensions.team_id), bin(timestamp, 1d)\n```'
                }
              }
            }
          }
          {
            position: {
              x: 6
              y: 9
              rowSpan: 3
              colSpan: 6
            }
            metadata: {
              type: 'Extension/HubsExtension/PartType/MarkdownPart'
              settings: {
                content: {
                  content: '# SLA Metrics\n\nKQL:\n```kusto\ncustomMetrics\n| where name in ("run_success_rate", "time_to_pr_minutes")\n| summarize AvgValue=avg(value) by name, bin(timestamp, 1d)\n```'
                }
              }
            }
          }
        ]
      }
    ]
    metadata: {
      model: {
        timeRange: {
          value: {
            relative: {
              duration: 24
              timeUnit: 1
            }
          }
          type: 'MsPortalFx.Composition.Configuration.ValueTypes.TimeRange'
        }
        filterLocale: {
          value: 'en-us'
        }
        filters: {
          value: {
            MsPortalFx_TimeRange: {
              model: {
                format: 'utc'
                granularity: 'auto'
                relative: '24h'
              }
              displayCache: {
                name: 'UTC Time'
                value: 'Past 24 hours'
              }
              filteredPartIds: []
            }
          }
        }
      }
    }
  })
  tags: {
    environment: environment
    project: projectName
    source: 'codecustodian'
    appInsightsId: appInsightsId
    logAnalyticsId: lawId
  }
}

output dashboardId string = dashboard.id
