# Token Efficiency & Quota Optimization Report

## Baseline

**Benchmark Mode:** Offline Scripted Fake Model  
**Timestamp:** 2026-10-27 16:40:23 UTC  
**Fixed Prompt Overhead:** ~2850 tokens (all 29 tool schemas + system instructions declared on every call)

---

### Scenario (a): Provisioning IaC & CI/CD Pipeline
**Prompt:** `Create the Terraform infrastructure for my project and prepare a CI/CD workflow`  
**API Calls:** 3  

| Call # | Iteration | Prompt Tokens | Output Tokens | Total Tokens |
| :--- | :--- | :--- | :--- | :--- |
| Call 1 | Iteration 1 | 2,882 | 92 | 2,974 |
| Call 2 | Iteration 2 | 3,021 | 84 | 3,105 |
| Call 3 | Iteration 3 | 3,229 | 58 | 3,287 |
| **Total** | - | **9,132** | **234** | **9,366** |

### Scenario (b): Diagnostic Kubernetes Troubleshooting
**Prompt:** `Why is my pod in CrashLoopBackOff?`  
**API Calls:** 3  

| Call # | Iteration | Prompt Tokens | Output Tokens | Total Tokens |
| :--- | :--- | :--- | :--- | :--- |
| Call 1 | Iteration 1 | 2,870 | 32 | 2,902 |
| Call 2 | Iteration 2 | 2,982 | 46 | 3,028 |
| Call 3 | Iteration 3 | 3,095 | 66 | 3,161 |
| **Total** | - | **8,947** | **144** | **9,091** |

### Scenario (c): Policy & Cost Estimation
**Prompt:** `Estimate cost for 4 replicas with postgres`  
**API Calls:** 2  

| Call # | Iteration | Prompt Tokens | Output Tokens | Total Tokens |
| :--- | :--- | :--- | :--- | :--- |
| Call 1 | Iteration 1 | 2,872 | 42 | 2,914 |
| Call 2 | Iteration 2 | 3,153 | 54 | 3,207 |
| **Total** | - | **6,025** | **96** | **6,121** |

---
## Baseline Summary Totals

| Metric | Value |
| :--- | :--- |
| **Total Scenarios Evaluated** | 3 |
| **Total API Calls Across Scenarios** | 8 |
| **Total Cumulative Prompt Tokens** | 24,104 |
| **Total Cumulative Output Tokens** | 474 |
| **Grand Total Tokens Consumed** | **24,578** |
| **Average Tokens Per Request** | 8,192 |
