WITH TeamBatting AS (
    SELECT
        yearID,
        teamID,
        SUM(AB) AS TotalAtBats,
        SUM(H) AS TotalHits,
        SUM(HR) AS TotalHR,
        SUM(H + "2B" + 2 * "3B" + 3 * HR) AS TotalBases
    FROM
        sports_analytics_catalog.curated.batting
    GROUP BY
        yearID, teamID
),

TeamSalaries AS (
    SELECT
        yearID,
        teamID,
        SUM(salary) AS TotalSalary
    FROM
        sports_analytics_catalog.curated.salaries
    GROUP BY
        yearID, teamID
)

SELECT
    b.teamID,
    b.yearID,
    s.TotalSalary AS total_payroll,
    b.TotalAtBats AS AB,
    b.TotalHR AS HR,
    ROUND(CAST(b.TotalHits AS DOUBLE) / NULLIF(b.TotalAtBats, 0), 3) AS BA,
    ROUND(CAST(b.TotalBases AS DOUBLE) / NULLIF(b.TotalAtBats, 0), 3) AS SLG,
    ROUND(CAST(b.TotalHR AS DOUBLE) / NULLIF(s.TotalSalary / 1000000.0, 0), 2) AS HR_per_Million
FROM
    TeamBatting b
LEFT JOIN
    TeamSalaries s
ON
    b.yearID = s.yearID AND b.teamID = s.teamID
ORDER BY
    b.yearID DESC, b.teamID;
