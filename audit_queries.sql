-- OSU P-Card audit (calendar year 2014) - SQLite queries for Parts II and III

-- ===== Part II  qry_T2_Question1
SELECT FullName,
       ROUND(SUM(Amount), 2) AS TotalSpent
FROM pcards
WHERE Year = 2014
GROUP BY FullName
HAVING SUM(Amount) > 50000
ORDER BY TotalSpent DESC;

-- ===== Part II  qry_T2_Question2
SELECT FullName,
       ROUND(SUM(Amount), 2) AS MonthlyTotal,
       Month
FROM pcards
WHERE Year = 2014
GROUP BY FullName, Month
HAVING SUM(Amount) > 10000
ORDER BY Month ASC, MonthlyTotal DESC;

-- ===== Part II  qry_T2_Question3
SELECT Amount, FullName, Description, Vendor,
       TransactionDate, PostedDate, MCC
FROM pcards
WHERE Year = 2014
  AND Amount > 5000
ORDER BY Amount DESC;

-- ===== Part II  qry_T2_Question4
SELECT p.Amount, p.FullName, p.Description, p.Vendor,
       p.TransactionDate, p.PostedDate, p.MCC
FROM pcards AS p
JOIN (SELECT FullName, Vendor, TransactionDate
      FROM pcards
      WHERE Year = 2014
      GROUP BY FullName, Vendor, TransactionDate
      HAVING COUNT(*) > 1
         AND SUM(Amount) > 5000) AS s
  ON  p.FullName = s.FullName
  AND p.Vendor = s.Vendor
  AND p.TransactionDate = s.TransactionDate
WHERE p.Year = 2014
ORDER BY date(printf('%04d-%02d-%02d', p.Year, p.Month, CAST(substr(p.TransactionDate, instr(p.TransactionDate, '/') + 1) AS INTEGER))) ASC,
         p.FullName, p.Vendor, p.Amount DESC;

-- ===== Part II  qry_T2_Question5
-- Exactly two transactions at one vendor on one day, by two DIFFERENT
-- cardholders (COUNT(*) = COUNT(DISTINCT FullName) = 2 excludes double payments)
SELECT p.Amount, p.FullName, p.Description, p.Vendor,
       p.TransactionDate, p.PostedDate, p.MCC
FROM pcards AS p
JOIN (SELECT Vendor, TransactionDate
      FROM pcards
      WHERE Year = 2014
      GROUP BY Vendor, TransactionDate
      HAVING COUNT(*) = 2
         AND COUNT(DISTINCT FullName) = 2
         AND SUM(Amount) > 5000) AS s
  ON  p.Vendor = s.Vendor
  AND p.TransactionDate = s.TransactionDate
WHERE p.Year = 2014
ORDER BY date(printf('%04d-%02d-%02d', p.Year, p.Month, CAST(substr(p.TransactionDate, instr(p.TransactionDate, '/') + 1) AS INTEGER))) ASC,
         p.Vendor, p.FullName;

-- ===== Part II  qry_T2_Question6
-- Exactly two transactions by one cardholder on one day, at two DIFFERENT
-- vendors (COUNT(*) = COUNT(DISTINCT Vendor) = 2 excludes double payments)
SELECT p.Amount, p.FullName, p.Description, p.Vendor,
       p.TransactionDate, p.PostedDate, p.MCC
FROM pcards AS p
JOIN (SELECT FullName, TransactionDate
      FROM pcards
      WHERE Year = 2014
      GROUP BY FullName, TransactionDate
      HAVING COUNT(*) = 2
         AND COUNT(DISTINCT Vendor) = 2
         AND SUM(Amount) > 5000) AS s
  ON  p.FullName = s.FullName
  AND p.TransactionDate = s.TransactionDate
WHERE p.Year = 2014
ORDER BY date(printf('%04d-%02d-%02d', p.Year, p.Month, CAST(substr(p.TransactionDate, instr(p.TransactionDate, '/') + 1) AS INTEGER))) ASC,
         p.FullName, p.Vendor;

-- ===== Part II  qry_T2_Question7
SELECT p.FullName, p.Amount, p.Description, p.Vendor,
       p.TransactionDate, p.PostedDate, p.MCC
FROM pcards AS p
JOIN (SELECT DISTINCT FullName, TransactionDate          -- hotel-stay days
      FROM pcards
      WHERE Year = 2014
        AND (MCC LIKE '%hotel%' OR MCC LIKE '%motel%'
             OR MCC LIKE '%resort%' OR MCC LIKE '%inn%')) AS h
  ON  p.FullName = h.FullName
  AND p.TransactionDate = h.TransactionDate
WHERE p.Year = 2014
  AND (p.MCC LIKE '%food%' OR p.MCC LIKE '%restaurant%')
ORDER BY p.FullName ASC, p.Amount ASC;

-- ===== Part II  qry_T2_Question8
-- Alcohol (prohibited): liquor-store / bar MCCs, liquor vendors, or beer/liquor
-- in the description ("alcohol" alone is avoided: it returns lab chemicals)
SELECT FullName, Amount, Description, Vendor, TransactionDate, MCC
FROM pcards
WHERE Year = 2014
  AND Amount > 0
  AND (MCC LIKE 'PACKAGE STORES--BEER,WINE%'
       OR MCC LIKE 'DRINKING PLACES%'
       OR Vendor LIKE '%LIQUOR%'
       OR Vendor LIKE 'WINE %' OR Vendor LIKE '% WINE%'
       OR Description LIKE '%beer%'
       OR Description LIKE '%liquor%')
ORDER BY Amount DESC;

-- ===== Part II  qry_T2_Question9
-- Gasoline (prohibited on the P-Card): service-station / fuel-dispenser MCCs,
-- summarised by cardholder so the heaviest users are reviewed first
SELECT FullName,
       COUNT(*)               AS NumTransactions,
       ROUND(SUM(Amount), 2)  AS TotalFuelSpend,
       ROUND(MAX(Amount), 2)  AS LargestPurchase
FROM pcards
WHERE Year = 2014
  AND Amount > 0
  AND (MCC LIKE 'SERVICE STATIONS%'
       OR MCC = 'AUTOMATED FUEL DISPENSER')
GROUP BY FullName
ORDER BY TotalFuelSpend DESC;

-- ===== Part II  qry_T2_Question10
-- Mail / postage (must go through University Mailing)
SELECT FullName, Amount, Description, Vendor, TransactionDate, MCC
FROM pcards
WHERE Year = 2014
  AND Amount > 0
  AND (MCC = 'POSTAGE STAMPS'
       OR Vendor LIKE 'USPS%'
       OR Vendor LIKE '%POST OFFICE%'
       OR Description LIKE '%postage%')
ORDER BY Amount DESC;

-- ===== Part II  qry_T2_Question11
-- Donations / sponsorships: charitable, political and religious organisations,
-- summarised by vendor
SELECT Vendor, MCC,
       COUNT(*)                  AS NumTransactions,
       COUNT(DISTINCT FullName)  AS NumCardholders,
       ROUND(SUM(Amount), 2)     AS TotalAmount
FROM pcards
WHERE Year = 2014
  AND Amount > 0
  AND (MCC LIKE 'CHARITABLE%'
       OR MCC LIKE 'POLITICAL ORGANIZATIONS%'
       OR MCC LIKE 'RELIGIOUS ORGANIZATIONS%'
       OR Description LIKE '%donation%'
       OR Description LIKE '%sponsor%')
GROUP BY Vendor, MCC
ORDER BY TotalAmount DESC;

-- ===== Part II  qry_T2_Question12
-- Personal / individual memberships and dues
SELECT FullName, Amount, Description, Vendor, TransactionDate, MCC
FROM pcards
WHERE Year = 2014
  AND Amount > 0
  AND (MCC LIKE 'MEMBERSHIP CLUBS%'
       OR Description LIKE '%membership%'
       OR Description LIKE '%dues%')
ORDER BY FullName, Amount DESC;

-- ===== Part II  qry_T2_Question13
-- Gifts, gift cards and items with no business purpose (flowers, candy)
SELECT FullName, Amount, Description, Vendor, TransactionDate, MCC
FROM pcards
WHERE Year = 2014
  AND Amount > 0
  AND (Description LIKE '%gift card%'
       OR Description LIKE '%gift cert%'
       OR Vendor LIKE '%gift card%'
       OR MCC = 'FLORISTS'
       OR MCC LIKE 'CANDY,NUT%'
       OR Description LIKE '%flower%'
       OR Description LIKE '%candy%')
ORDER BY Amount DESC;

-- ===== Part II  qry_T2_Question14
-- Purchases from University departments/auxiliaries (should use the CVI system)
SELECT Vendor,
       COUNT(*)                  AS NumTransactions,
       COUNT(DISTINCT FullName)  AS NumCardholders,
       ROUND(SUM(Amount), 2)     AS TotalAmount
FROM pcards
WHERE Year = 2014
  AND Amount > 0
  AND (Vendor LIKE 'OSU %' OR Vendor LIKE 'OSU-%'
       OR Vendor LIKE 'OKLAHOMA STATE U%')
GROUP BY Vendor
ORDER BY TotalAmount DESC;

-- ===== Part III qry_T3_Question1
SELECT CAST(substr(CAST(Amount AS TEXT), 1, 1) AS INTEGER) AS FirstDigit,
       COUNT(*) AS NumTransactions,
       ROUND(100.0 * COUNT(*) /
             (SELECT COUNT(*) FROM pcards WHERE Year = 2014 AND Amount >= 1), 3)
             AS ActualPercent,
       ROUND(100.0 * CASE CAST(substr(CAST(Amount AS TEXT), 1, 1) AS INTEGER)
             WHEN 1 THEN 0.30103 WHEN 2 THEN 0.17609 WHEN 3 THEN 0.12494
             WHEN 4 THEN 0.09691 WHEN 5 THEN 0.07918 WHEN 6 THEN 0.06695
             WHEN 7 THEN 0.05799 WHEN 8 THEN 0.05115 WHEN 9 THEN 0.04576 END, 3)
             AS BenfordPercent
FROM pcards
WHERE Year = 2014
  AND Amount >= 1
GROUP BY FirstDigit
ORDER BY FirstDigit;

-- ===== Part III qry_T3_Question2
SELECT p.TransactionDate, p.Vendor, p.FullName, p.Amount
FROM pcards AS p
JOIN (SELECT TransactionDate, Vendor, CardholderFirstInitial,
             CardholderLastName, Amount
      FROM pcards
      WHERE Year = 2014 AND Amount > 0
      GROUP BY TransactionDate, Vendor, CardholderFirstInitial,
               CardholderLastName, Amount
      HAVING COUNT(*) > 1) AS d
  ON  p.TransactionDate = d.TransactionDate
  AND p.Vendor = d.Vendor
  AND p.CardholderFirstInitial = d.CardholderFirstInitial
  AND p.CardholderLastName = d.CardholderLastName
  AND p.Amount = d.Amount
WHERE p.Year = 2014 AND p.Amount > 0
ORDER BY date(printf('%04d-%02d-%02d', p.Year, p.Month, CAST(substr(p.TransactionDate, instr(p.TransactionDate, '/') + 1) AS INTEGER))) ASC,
         p.Vendor ASC;

-- ===== Part III qry_T3_Question3
SELECT FullName,
       COUNT(*)                    AS DuplicateOccasions,
       SUM(Copies)                 AS DuplicateRows,
       ROUND(SUM(ExtraAmount), 2)  AS PotentialOverpayment
FROM (SELECT FullName, TransactionDate, Vendor, Amount,
             COUNT(*) AS Copies,
             (COUNT(*) - 1) * Amount AS ExtraAmount
      FROM pcards
      WHERE Year = 2014 AND Amount > 0
      GROUP BY TransactionDate, Vendor, CardholderFirstInitial,
               CardholderLastName, Amount
      HAVING COUNT(*) > 1)
GROUP BY FullName
ORDER BY DuplicateOccasions DESC, PotentialOverpayment DESC;

-- ===== Part III qry_T3_Question4
SELECT Amount, Vendor, Description, FullName
FROM pcards
WHERE Year = 2014
  AND Amount > 0
  AND CAST(Amount AS INTEGER) BETWEEN 1000 AND 9999
  AND CAST(Amount AS INTEGER) % 1000 = 0
ORDER BY Vendor ASC, FullName ASC;

-- ===== Part III qry_T3_Question5
-- Transactions just below the $5,000 single-transaction limit ($4,500-$4,999.99),
-- by cardholder: repeated near-limit buying suggests limit awareness / evasion
SELECT FullName,
       COUNT(*)               AS NearLimitTxns,
       ROUND(SUM(Amount), 2)  AS NearLimitTotal,
       GROUP_CONCAT(DISTINCT Vendor) AS Vendors
FROM pcards
WHERE Year = 2014
  AND Amount >= 4500 AND Amount < 5000
GROUP BY FullName
HAVING COUNT(*) >= 3
ORDER BY NearLimitTxns DESC, NearLimitTotal DESC;

-- ===== Part III qry_T3_Question6
-- Weekend purchases at non-travel merchants (>= $250): employees rarely buy
-- supplies for the University on Saturdays/Sundays, so these are personal-use risks
SELECT FullName,
       COUNT(*)               AS WeekendTxns,
       ROUND(SUM(Amount), 2)  AS WeekendTotal,
       ROUND(MAX(Amount), 2)  AS LargestTxn
FROM pcards
WHERE Year = 2014
  AND Amount >= 250
  AND strftime('%w', date(printf('%04d-%02d-%02d', Year, Month, CAST(substr(TransactionDate, instr(TransactionDate, '/') + 1) AS INTEGER)))) IN ('0', '6')
  AND MCC NOT LIKE '%hotel%' AND MCC NOT LIKE '%inn%'
  AND MCC NOT LIKE '%motel%' AND MCC NOT LIKE '%resort%'
  AND MCC NOT LIKE '%suites%' AND MCC NOT LIKE '%air%'
  AND MCC NOT LIKE '%rent%' AND MCC NOT LIKE '%travel%'
  AND MCC NOT LIKE '%restaurant%' AND MCC NOT LIKE '%eating%'
  AND MCC NOT LIKE '%lodging%' AND MCC NOT LIKE '%marriott%'
  AND Description NOT IN ('AIR TRAVEL', 'ROOM CHARGES', 'CAR RENTAL')
GROUP BY FullName
HAVING COUNT(*) >= 5
ORDER BY WeekendTotal DESC;

-- ===== Part III qry_T3_Question7
-- Vendors used by only ONE cardholder in 2014 but receiving >= $15,000:
-- possible fictitious vendor, kickback or conflict-of-interest relationship
SELECT Vendor, MAX(FullName) AS OnlyCardholder, MCC,
       COUNT(*)               AS NumTxns,
       ROUND(SUM(Amount), 2)  AS TotalPaid
FROM pcards
WHERE Year = 2014
  AND Amount > 0
GROUP BY Vendor
HAVING COUNT(DISTINCT FullName) = 1
   AND SUM(Amount) >= 15000
ORDER BY TotalPaid DESC;

-- ===== Part III qry_T3_Question8
-- Personal-benefit merchants: health, beauty, jewelry and pawn-type MCCs rarely
-- serve a University purpose, so spending there may be personal use of the card
SELECT FullName, MCC,
       COUNT(*)                     AS NumTxns,
       ROUND(SUM(Amount), 2)        AS TotalSpent,
       GROUP_CONCAT(DISTINCT Vendor) AS Vendors
FROM pcards
WHERE Year = 2014
  AND Amount > 0
  AND (MCC IN ('OPTICIANS AND DISPENSING', 'OPTOMETRISTS AND OPTHAMOLOGISTS',
               'CHIROPRACTORS', 'DENTISTS AND ORTHODONTISTS',
               'HEALTH AND BEAUTY SPAS', 'BEAUTY AND BARBER SHOPS',
               'COSMETIC STORES', 'PAWN SHOPS',
               'COUNSELING SERVICES--DEBT,MARRIAGE,PERSONAL',
               'JEWELRY,WATCH,CLOCK,AND SILVERWARE STORES',
               'PRECIOUS STONES AND METALS, WATCHES & JEWELRY')
       OR MCC LIKE 'DOCTORS AND PHYSICIANS%')
GROUP BY FullName, MCC
ORDER BY TotalSpent DESC;
