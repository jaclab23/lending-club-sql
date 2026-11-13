SELECT CASE 
	WHEN fico IS NULL THEN 'unknown'
	WHEN fico < 680 THEN '1. < 680'
	WHEN (fico <= 699) AND (fico>=680) THEN '2. 680-699'	WHEN (fico <= 719) AND (fico>=700) THEN '3. 700-719'
	WHEN (fico <= 739) AND (fico>=720) THEN '4. 720-739'
	WHEN (fico <= 759) AND (fico>=740) THEN '5. 740-759'
	WHEN (fico>=760) THEN '6. 760+'
END AS fico_band, COUNT(*) AS Count
,ROUND(AVG(default_flag*100.0),2) AS DefaultRate
from fact_loan
GROUP BY fico_band
ORDER BY fico_band