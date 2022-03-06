# SOFROnIndex_v02

* Fetch Data from Fed using XML web service
  * All available overnight SOFR rates
  * All available cumulative SOFR Index values 
* Calculate Accruals
  * Determine all accrual periods between any two days within a test period
  * Calculate accruals using compounding with a) overnight rates and b) using SOFR Index, convert to annual rates
* Report Differences
  * Group results into term buckets, up to 1 month, 3 month, 6 month and longer
  * Round results to various levels of precision (standard is 5 decimal places, e.g.,  0.01234 = 1.234%)
  * For each precision level, group results which differ after rounding (e.g., at 5 decimnals 1.234% vs 1.235%)
  * Show the number and % of results which differ
