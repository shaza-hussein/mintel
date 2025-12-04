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





COMPHERSIVE_DAILY_SUB_QUERY: str = """--sql
-- daily subscription for users with their info, and the most used mobile in the current month
WITH d_filtered AS (
    SELECT
        tbl_dt, msisdn, bundle_id, bundle_name, bundle_type,
        validity, price, subscriptions, configured_volume,
        usage_type, total_amount, volume, call_duration,
        category_description, service_class_category,
        product_category, canal, payment_mode,
        business_categorisation, dynamic_speed,
        cell_id
    FROM facts.fact_bundle_subscription
    WHERE tbl_dt BETWEEN 20250901 AND 20250930
      AND subscriptions != 0
      AND total_amount != 0
),
customers_info AS (
    SELECT 
        msisdn_key,
        arbitrary(gender_v) AS gender_v,
        arbitrary(date_of_birth_d) AS date_of_birth_d
    FROM feeds.gsm_service_mast
    WHERE tbl_dt BETWEEN 20250901 AND 20250930
    AND msisdn_key != -1
    GROUP BY msisdn_key
),
device_usage_by_month AS ( 
    SELECT 
        msisdn,
        device_capability,
        model_name,
        brand_name,
        COUNT(*) AS usage_count
    FROM 
        facts.fact_ceo_daily_localized_new
    WHERE 
        tbl_dt BETWEEN 20250901 AND 20250930
        AND rgs_90_excl_loy = 1
    GROUP BY 
        msisdn, device_capability, model_name, brand_name
), 
ranked_devices_by_month AS (
    SELECT 
        *,
        ROW_NUMBER() OVER (PARTITION BY msisdn ORDER BY usage_count DESC) AS rank
    FROM device_usage_by_month
),
most_used_device_by_month AS (
    SELECT 
        msisdn,
        device_capability,
        model_name,
        brand_name
    FROM ranked_devices_by_month
    WHERE rank = 1
)
SELECT
    d.tbl_dt,
    d.msisdn,
    c.gender_v       AS gender,
    c.date_of_birth_d AS date_of_birth,
    d.bundle_id, d.bundle_name, d.bundle_type, d.validity,
    d.price, d.subscriptions, d.configured_volume, d.usage_type,
    d.total_amount AS total_rev,
    d.volume,
    d.call_duration,
    d.category_description, d.service_class_category,
    d.product_category, d.canal, d.payment_mode,
    d.business_categorisation, d.dynamic_speed,
    d.cell_id, l.cell_name, l.site_id, l.site_name,
    l.latitude, l.longitude, l.department_city, l.technology,
    m.model_name, m.brand_name, m.device_capability
FROM d_filtered d
LEFT JOIN customers_info c 
    ON c.msisdn_key = CAST(d.msisdn AS BIGINT)
LEFT JOIN most_used_device_by_month m
	ON m.msisdn = d.msisdn
LEFT JOIN facts.dim_location_cell_id_new l
 	ON d.cell_id = l.cell_id
"""