# NCDEQ — Wastewater Discharge Monitoring Requirements

## NPDES Permit Monitoring

All NPDES wastewater discharge permits in North Carolina require routine monitoring. The following parameters are commonly required based on permit type:

### Municipal Wastewater (Typical Parameters)
| Parameter | EPA Method | Frequency | Units |
|---|---|---|---|
| BOD₅ | SM 5210B | Weekly | mg/L |
| TSS | SM 2540D | Weekly | mg/L |
| NH₃-N (Ammonia) | EPA 350.1 | Weekly | mg/L |
| TKN | EPA 351.2 | Monthly | mg/L |
| Total Phosphorus | EPA 365.1 | Monthly | mg/L |
| Fecal Coliform | SM 9222D | Weekly | CFU/100mL |
| pH | SM 4500-H+ | Daily | SU |
| Dissolved Oxygen | SM 4500-O | Daily | mg/L |
| Flow | Continuous | Continuous | MGD |
| Oil & Grease | EPA 1664A | Monthly | mg/L |

### Industrial Wastewater (Additional Parameters)
| Parameter | EPA Method | Notes |
|---|---|---|
| COD | SM 5220D | Chemical Oxygen Demand |
| Total Metals | EPA 200.8 | ICP-MS scan |
| Cyanide | EPA 335.4 | Required for metal finishing |
| Phenols | EPA 420.1 | |
| VOCs | EPA 624.1 | Volatile Organic Compounds |
| SVOCs | EPA 625.1 | Semi-Volatile Organic Compounds |

## NCDEQ Submission Requirements
- **Electronic reporting** via NetDMR is required for all NPDES permits
- **Discharge Monitoring Reports (DMRs)** due by the 28th of the following month
- **Grab samples** must be collected during representative discharge periods
- **Composite samples** typically 24-hour flow-proportional
- **Hold times** must be strictly adhered to — exceedances invalidate results

## EDD Format Requirements (NCDEQ)
- File format: CSV or pipe-delimited
- Required fields: Facility ID, Permit Number, Monitoring Location, Parameter Code, Sample Date, Sample Time, Result Value, Result Units, Method Code, MDL, RL, Qualifier Flag
- Common rejection reasons:
  - Missing parameter codes
  - Incorrect date format (must be MM/DD/YYYY)
  - Results below MDL reported as "0" instead of "<MDL"
  - Missing monitoring location identifiers
  - Qualifier flags not matching NCDEQ code list

## Key NCDEQ Contacts
- Division of Water Resources: (919) 707-9000
- NPDES Permitting Unit: npdes.info@deq.nc.gov
- Compliance & Enforcement: (919) 707-3600
