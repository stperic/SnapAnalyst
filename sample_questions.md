# Sample Questions for SnapAnalyst

Use the `|` separator to split SQL queries from analysis instructions:
**Format**: `<SQL_QUESTION> | <ANALYSIS_INSTRUCTIONS>`

---

## 1. Error Analysis by Type

### Basic Questions
```
What are the most common error types?
Show income errors by state
Find all household composition errors
Show deduction errors for elderly households
```

### With Focused Analysis (using |)
```
What are the most common error types? | Focus on the top 3 and explain possible root causes

Show errors by element code | Compare income errors (311-346) vs deduction errors (361-366)

Find all errors | Highlight which states have the highest income reporting errors
```

---

## 2. Errors by Household Characteristics

```
Show households with overissuance | Compare households with children vs elderly

What's the error rate for categorically eligible households? | Explain why they might have different error patterns

Show expedited service cases with errors | Focus on households that didn't receive service on time

Find households with high benefit relative to income | Identify potential reporting issues
```

---

## 3. Income-Related Errors (Most Common)

```
Show all wage errors (element 311) | Which states have the most and why might that be?

What's the total error amount by income type? | Compare wages vs social security vs SSI errors

Find unreported income errors (nature 35) | Show state patterns and common characteristics

Show households with income changes | Identify which might have reporting errors
```

---

## 4. State-Level Analysis

```
Compare error rates across states | Focus on states with BBCE vs non-BBCE policies

Show average error amounts by state | Identify outliers and possible system issues

Which states have the most computation errors (element 520)? | Suggest potential system improvements

Show error patterns by state | Compare states with simplified reporting vs change reporting
```

---

## 5. Household Composition Analysis

```
Find household composition errors (element 150) | Show patterns by household size

Show errors for households with elderly members | Compare to households without elderly

What's the error rate for multi-person households? | Focus on households with 4+ members

Find ineligible members in households | Analyze snap_affiliation_code patterns
```

---

## 6. Benefit Amount Analysis

```
Show households receiving maximum benefits | What's their error rate?

Find households with small benefits relative to income | Potential underreporting?

Compare error amounts for households at different benefit levels | Identify risk thresholds

Show benefit errors by household size | Is there a pattern with larger households?
```

---

## 7. Deduction Errors

```
Find all shelter deduction errors (element 363) | Which states need better verification?

Show deduction errors for elderly/disabled households | Different pattern than general population?

Compare medical expense deduction errors (365) by state | Focus on states with highest rates

What's the total dollar amount of deduction errors? | Break down by deduction type
```

---

## 8. Agency vs Client Responsibility

```
Show errors by responsibility | Compare agency errors (10-21) vs client errors (1-8)

Find policy application errors (agency 10) | Which states and error types?

Show unreported income cases | Is it more agency (16) or client (1) responsibility?

Compare agency vs client errors by state | Identify states needing training vs outreach
```

---

## 9. Time-Based Analysis

```
Show error rates by fiscal year | Are errors improving or getting worse?

Compare error patterns 2021 vs 2023 | Focus on income errors and what changed

Find households with multiple errors | Timeline analysis
```

---

## 10. Advanced Analysis

```
Show overissuance cases with high income uncertainty | Calculate benefit to max allotment ratio and flag outliers

Find income errors for categorically eligible households | Should they have income verification?

Compare error rates for expedited vs non-expedited cases | Focus on states with highest differences

Show households living above reported means | Flag cases where expenses exceed income

Identify high-risk profiles for recertification | Households with prior errors + income changes
```

---

## 11. Root Cause Investigation

```
Show wage errors (311) with nature code | Break down by unreported (35) vs incorrect amount (38)

Find computation errors (520) by state | Which states might need system updates?

Show element + nature combinations | Identify the most common error patterns

Compare error findings (2,3,4) by element type | Which errors lead to ineligibility?
```

---

## 12. Practical Management Questions

```
What's our total dollar exposure from errors? | Focus on top 5 states

Show errors that could have been caught at certification | Element codes 311, 150, 211

Which error types have increased over time? | Compare 2021-2023 trends by element

Find households with cascading errors | Multiple element codes per case
```

---

## Quick Reference: Common Codes

### Element Codes (Error Types)
- **311**: Wages and salaries
- **331**: RSDI (Social Security)
- **333**: SSI
- **334**: Unemployment
- **150**: Household composition
- **211**: Bank accounts/cash
- **363**: Shelter deduction
- **520**: Computation errors

### Nature Codes (What Went Wrong)
- **35**: Unreported income
- **37**: Income known but not included
- **38**: More income than budgeted
- **75**: Benefit incorrectly computed

### Status Codes
- **1**: Amount correct
- **2**: Overissuance
- **3**: Underissuance

---

**Note**: Edit this file to add your team's frequently used queries!
