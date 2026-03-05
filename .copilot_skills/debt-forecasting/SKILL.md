---
name: debt-forecasting
description: >
  Technical debt trend analysis, predictive forecasting, remediation
  velocity optimization, and sprint planning integration.
---

# Debt Forecasting Skill

## Trend Interpretation

### Trend Classification
- **Improving** (slope < -0.05/day): Active remediation exceeds new debt introduction
- **Stable** (slope -0.05..0.05/day): Debt creation and remediation are balanced
- **Worsening** (slope > 0.05/day): New debt is accumulating faster than fixes

### Reading Forecast Data
```
Predicted: 85 findings in 90 days (CI: 72-98)
Trend: worsening (+0.14 findings/day)
Hotspots: security (+12), code_smell (+8)
```
- The **confidence interval** widens with fewer data points
- **Hotspot categories** show which finding types are growing fastest
- **Slope** is the most actionable metric — daily rate of change

## Remediation Velocity

### Calculating ROI
- **Current velocity** = findings_fixed / sprint_duration
- **Target velocity** = current_findings / desired_paydown_sprints
- **Gap** = target - current → engineer-days needed to close

### Sprint Planning Integration
1. Pull the latest forecast before sprint planning
2. Identify hotspot categories — assign specialist reviewers
3. Set sprint remediation target = 1.5× current creation rate (to make progress)
4. Track actual velocity against forecast — adjust next sprint

## Forecasting Best Practices

### Data Quality
- Run scans consistently (same scanners, same config) for comparable snapshots
- Minimum 3 snapshots needed; 10+ snapshots give reliable forecasts
- Weekly scans produce actionable 90-day forecasts
- Daily scans during active remediation for real-time velocity tracking

### Action Triggers
| Trend | Slope | Recommended Action |
|-------|-------|--------------------|
| Worsening | >0.5/day | Emergency remediation sprint |
| Worsening | 0.1–0.5/day | Allocate 20% sprint capacity to debt |
| Stable | ±0.05/day | Maintain current practices |
| Improving | <-0.1/day | Celebrate, then raise scanner thresholds |

### Communicating to Stakeholders
- Use **predicted finding counts** for budget justification
- Use **confidence intervals** to set expectations
- Compare **predicted vs actual** to demonstrate CodeCustodian ROI
- Track **velocity trend** quarterly for engineering health reports
