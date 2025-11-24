# This file contains the queries used to pull the datasets from the opreaotr Database.


# --------------------------------------------
# This represents the information for each bundle, from the bundle's perspective.
# --------------------------------------------
DAILY_BASE_BUNDLES_INFO: str = """--sql
WITH daily_base_bundle_info AS ( -- daily base bundles information
	SELECT tbl_dt, 
		   bundle_id, 
		   bundle_name, 
		   bundle_type, 
		   validity,
		   price,
		   usage_type,
		   configured_volume,
		   service_class_category,
		   SUM(call_duration)/60 AS duration,
		   SUM(total_amount) AS total_rev,
		   SUM(subscriptions) AS total_subscriptions,
		   SUM(coalesce(TRS,0)) AS sessions,
		   COUNT(DISTINCT msisdn) AS daily_unq_users,
	FROM facts.fact_bundle_subscription 
	WHERE tbl_dt BETWEEN 20250101 AND 20251030
		AND subscriptions != 0
		AND total_amount != 0
		AND bundle_name IS NOT NULL
		AND bundle_type IS NOT NULL
	GROUP BY tbl_dt,
			 bundle_id, bundle_name , bundle_type, validity, price, usage_type, configured_volume, service_class_category
) 
SELECT *
FROM daily_base_bundle_info
"""


WEEKLY_BASE_BUNDLES_INFO: str = """--sql
WITH weekly_base_bundle_info AS ( -- weekly base bundles information
    SELECT 
        week(date_parse(CAST(tbl_dt AS varchar), '%Y%m%d')) AS week_number,
        year(date_parse(CAST(tbl_dt AS varchar), '%Y%m%d')) AS year_number,
        bundle_id, 
        bundle_name, 
        bundle_type, 
        validity,
        price,
        usage_type,
        configured_volume,
        service_class_category,
        SUM(call_duration)/60 AS total_duration,
        SUM(total_amount) AS total_rev,
        SUM(subscriptions) AS total_subscriptions,
        SUM(coalesce(TRS,0)) AS total_sessions,
        COUNT(DISTINCT msisdn) AS unique_users
    FROM facts.fact_bundle_subscription 
    WHERE tbl_dt BETWEEN 20250101 AND 20251030
        AND subscriptions != 0
        AND total_amount != 0
        AND bundle_name IS NOT NULL 
        AND bundle_type IS NOT NULL
    GROUP BY 
        week(date_parse(CAST(tbl_dt AS varchar), '%Y%m%d')),
        year(date_parse(CAST(tbl_dt AS varchar), '%Y%m%d')),
        bundle_id, bundle_name, bundle_type, validity, price, usage_type, 
        configured_volume, service_class_category
) 
SELECT *
FROM weekly_base_bundle_info
ORDER BY year_number, week_number
"""


MONTHLY_BASE_BUNDLES_INFO: str = """--sql
WITH monthly_base_bundle_info AS ( -- monthly base bundles information
    SELECT 
        month(date_parse(CAST(tbl_dt AS varchar), '%Y%m%d')) AS month_number, 
        year(date_parse(CAST(tbl_dt AS varchar), '%Y%m%d')) AS year_number,
        bundle_id, 
        bundle_name, 
        bundle_type, 
        validity,
        price,
        usage_type,
        configured_volume,
        service_class_category,
        SUM(call_duration)/60 AS total_duration,
        SUM(total_amount) AS total_rev,
        SUM(subscriptions) AS total_subscriptions,
        SUM(coalesce(TRS,0)) AS total_sessions,
        COUNT(DISTINCT msisdn) AS unique_users
    FROM facts.fact_bundle_subscription 
    WHERE tbl_dt BETWEEN 20250101 AND 20251030
        AND subscriptions != 0
        AND total_amount != 0
        AND bundle_name IS NOT NULL 
        AND bundle_type IS NOT NULL
    GROUP BY 
        month(date_parse(CAST(tbl_dt AS varchar), '%Y%m%d')),
        year(date_parse(CAST(tbl_dt AS varchar), '%Y%m%d')),
        bundle_id, bundle_name, bundle_type, validity, price, usage_type, 
        configured_volume, service_class_category
) 
SELECT *
FROM monthly_base_bundle_info
ORDER BY year_number, month_number
"""


# --------------------------------------------
# This represents the information of users of each bundle, from the sers of bundle's perspective.
# --------------------------------------------


