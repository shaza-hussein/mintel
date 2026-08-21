import re
import json
from .config import logger, DATA_PATH, COLUMNS_TO_EXCLUDE

# (Keep your Regex Patterns and Dictionaries here: TYPE_MAP, patterns, UNIT_MAP, etc.)
TYPE_MAP = {'BUNDLE_VOICE': 'VOICE', 'BUNDLE_SMS': 'SMS', 'BUNDLE_DATA': 'DATA'}
_NAME_DATA_PATTERNS = [(r'(\d[\d,.]*)\s*gb', 'GB'), (r'(\d[\d,.]*)\s*go', 'GB'), (r'(\d[\d,.]*)\s*mb', 'MB'), (r'(\d[\d,.]*)\s*mo', 'MB')]
_VOICE_COMPOUND_RE = re.compile(r'(\d[\d,.]*)\s*(?:mins?|mn)[^,]*?(\d[\d,.]*)\s*(?:sec|s)\b', re.IGNORECASE)

def _unit_from_name(bundle_name):
    name_lower = str(bundle_name).lower()
    for pat, unit in _NAME_DATA_PATTERNS:
        if re.search(pat, name_lower, re.IGNORECASE):
            return unit
    return 'MB'

def parse_volumes_to_json(volume_str, bundle_type, bundle_name):
    vol_MB, vol_min, vol_SMS = 0.0, 0.0, 0.0
    if not volume_str or str(volume_str).strip().lower() in ('nan', 'none', ''):
        return json.dumps({"MB": vol_MB, "MIN": vol_min, "SMS": vol_SMS})

    v = str(volume_str).strip().lower()
    btype = TYPE_MAP.get(str(bundle_type).upper().strip(), str(bundle_type).upper().strip())
    name_lower = str(bundle_name).lower() if bundle_name else ''

    if v in ('unlimited', 'illimité', 'illimitée', 'unlimitée', 'infini', '-1', '-1.0'):
        if btype == 'VOICE': vol_min = -1.0
        elif btype == 'SMS': vol_SMS = -1.0
        elif btype == 'DATA': vol_MB = -1.0
        else:
            if 'sms' in name_lower: vol_SMS = -1.0
            elif 'voix' in name_lower or 'min' in name_lower: vol_min = -1.0
            else: vol_MB = -1.0
        return json.dumps({"MB": vol_MB, "MIN": vol_min, "SMS": vol_SMS})

    compound = _VOICE_COMPOUND_RE.search(v)
    if compound:
        mins = float(compound.group(1).replace(',', '.'))
        secs = float(compound.group(2).replace(',', '.'))
        vol_min = round(mins + secs / 60, 4)
        return json.dumps({"MB": vol_MB, "MIN": vol_min, "SMS": vol_SMS})

    m = re.search(r'(\d[\d,.]*)\s*([a-zA-Z]*)', v.replace('\xa0', ' '))
    if not m:
        return json.dumps({"MB": vol_MB, "MIN": vol_min, "SMS": vol_SMS})

    num_str = m.group(1).replace(' ', '').replace(',', '.')
    unit_str = m.group(2).strip().lower()

    try:
        num = float(num_str)
    except ValueError:
        return json.dumps({"MB": vol_MB, "MIN": vol_min, "SMS": vol_SMS})

    actual_unit = unit_str.upper()
    if actual_unit in ('GB', 'GO', 'G'): vol_MB = round(num * 1024, 4)
    elif actual_unit in ('MB', 'MO'): vol_MB = num
    elif actual_unit in ('MIN', 'MINS', 'MN'): vol_min = num
    elif actual_unit == 'SMS': vol_SMS = int(num)
    elif actual_unit == '':
        if btype == 'VOICE': vol_min = num
        elif btype == 'SMS': vol_SMS = int(num)
        else: 
            inferred = _unit_from_name(bundle_name)
            if inferred == 'GB': vol_MB = round(num * 1024, 4)
            else: vol_MB = num
    else: vol_MB = num

    return json.dumps({"MB": vol_MB, "MIN": vol_min, "SMS": vol_SMS})

class DataCleaner:
    def __init__(self, con):
        self.con = con

    def execute_base_cleaning(self):
        logger.info("Starting base data cleaning and exclusions...")
        preprocess_query = f"""
        CREATE OR REPLACE TABLE clean_final_data AS 
        SELECT DISTINCT * EXCLUDE ({COLUMNS_TO_EXCLUDE})
        FROM read_parquet('{DATA_PATH}')
        WHERE msisdn IS NOT NULL AND tbl_dt IS NOT NULL
          AND bundle_id IS NOT NULL AND bundle_name IS NOT NULL
          AND bundle_type IS NOT NULL
          AND COALESCE(product_category, '') NOT IN ('DIY', 'STAFF', 'VAS')
          AND bundle_name NOT ILIKE '%DIY%'
          AND COALESCE(canal, '') != 'KDO'
        """
        self.con.sql(preprocess_query)
        final_count = self.con.sql("SELECT COUNT(*) FROM clean_final_data").fetchone()[0]
        logger.info("Base cleaning complete. Target table created. Rows: %d", final_count)

    def process_prices(self):
        logger.info("Processing price column...")
        clean_price_query = """
        CREATE OR REPLACE TABLE clean_final_data AS 
        WITH RegexCleaned AS (
            SELECT *,
                price AS original_price, 
                regexp_replace(CAST(price AS VARCHAR), '[^0-9.,]', '', 'g') AS price_numeric_chars,
                regexp_extract(bundle_name, '@([0-9]+)', 1) AS price_from_bundle
            FROM clean_final_data
        ),
        FormattedPrice AS (
            SELECT *,
                TRY_CAST(
                    CASE 
                        WHEN price_numeric_chars LIKE '%,%.%' THEN REPLACE(price_numeric_chars, ',', '')
                        WHEN price_numeric_chars LIKE '%,%' THEN REPLACE(price_numeric_chars, ',', '.')
                        WHEN TRY_CAST(price_numeric_chars AS DOUBLE) IS NOT NULL THEN price_numeric_chars
                        WHEN price_from_bundle IS NOT NULL THEN price_from_bundle
                        ELSE NULL
                    END AS DOUBLE
                ) AS price_clean
            FROM RegexCleaned
        )
        SELECT * EXCLUDE (price, price_numeric_chars, price_from_bundle, original_price), price_clean AS price
        FROM FormattedPrice;
        """
        self.con.sql(clean_price_query)
        self.con.sql("DELETE FROM clean_final_data WHERE price IS NULL;")
        logger.info("Price processing complete. Null prices removed.")

    def process_validity(self):
        logger.info("Processing validity column...")
        validity_query = """
        CREATE OR REPLACE TABLE clean_final_data AS 
        WITH ExtractedData AS (
            SELECT *,
                TRY_CAST(REGEXP_EXTRACT(LOWER(validity), '[0-9]+(\\.[0-9]+)?') AS DOUBLE) AS extracted_number,
                LOWER(CAST(validity AS VARCHAR)) AS val_text
            FROM clean_final_data
        )
        SELECT * EXCLUDE (extracted_number, val_text, validity),
            CASE 
                WHEN val_text LIKE '%month%' THEN extracted_number * 30.0 * 24.0
                WHEN val_text LIKE '%day%' THEN extracted_number * 24.0
                WHEN val_text LIKE '%hour%' THEN extracted_number
                ELSE extracted_number
            END AS validity
        FROM ExtractedData;
        """
        self.con.sql(validity_query)
        logger.info("Validity processing complete.")

    def process_volumes(self):
        logger.info("Disentangling volume attributes via UDF...")
        try:
            self.con.remove_function('parse_volumes_udf')
        except Exception:
            pass 

        self.con.create_function(
            'parse_volumes_udf', parse_volumes_to_json, 
            ['VARCHAR', 'VARCHAR', 'VARCHAR'], 'VARCHAR', null_handling='SPECIAL'
        )

        query = """
        CREATE OR REPLACE TABLE clean_final_data AS 
        WITH ParsedJSON AS (
            SELECT *,
                parse_volumes_udf(
                    CAST(configured_volume AS VARCHAR), 
                    CAST(bundle_type AS VARCHAR), 
                    CAST(bundle_name AS VARCHAR)
                ) AS volume_json
            FROM clean_final_data
        )
        SELECT * EXCLUDE (configured_volume, volume_json),
            CAST(json_extract_string(volume_json, '$.MB') AS DOUBLE) AS data_volume_mb,
            CAST(json_extract_string(volume_json, '$.MIN') AS DOUBLE) AS voice_volume_min,
            CAST(json_extract_string(volume_json, '$.SMS') AS DOUBLE) AS sms_volume_count
        FROM ParsedJSON;
        """
        self.con.sql(query)
        logger.info("Volume extraction complete. Splitted into orthogonal numeric features.")

    def finalize_schema(self):
        filter_columns_query = """
        CREATE OR REPLACE TABLE final_model_data AS 
        SELECT msisdn, bundle_id, tbl_dt, bundle_name, bundle_type, product_category,
               service_class_category, price, validity, data_volume_mb, voice_volume_min, sms_volume_count
        FROM clean_final_data;
        """
        self.con.sql(filter_columns_query)
        logger.info("Schema finalized to target features. Ready for K-Core.")