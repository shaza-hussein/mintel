from .config import logger, PROCESSED_PATH

class KCoreFilter:
    def __init__(self, con):
        self.con = con

    def execute(self, min_item_freq=5, min_user_freq=3):
        logger.info("Starting Iterative K-Core Filtering...")
        self.con.sql("CREATE OR REPLACE TABLE kcore_data AS SELECT * FROM final_model_data;")

        iteration = 1
        while True:
            old_count = self.con.sql("SELECT COUNT(*) FROM kcore_data").fetchone()[0]
            logger.info("Iteration %d: Current Rows = %d", iteration, old_count)

            self.con.sql(f"""
                CREATE OR REPLACE TABLE kcore_data AS
                SELECT * FROM kcore_data
                WHERE bundle_id IN (
                    SELECT bundle_id FROM kcore_data GROUP BY bundle_id HAVING COUNT(*) >= {min_item_freq}
                );
            """)
            
            self.con.sql(f"""
                CREATE OR REPLACE TABLE kcore_data AS
                SELECT * FROM kcore_data
                WHERE msisdn IN (
                    SELECT msisdn FROM kcore_data GROUP BY msisdn HAVING COUNT(*) >= {min_user_freq}
                );
            """)

            new_count = self.con.sql("SELECT COUNT(*) FROM kcore_data").fetchone()[0]
            if old_count == new_count:
                logger.info("Equilibrium reached. K-Core filtering completed.")
                break
            iteration += 1

    def export_checkpoints(self):
        full_data_path = f"{PROCESSED_PATH}/kcore_filtered_data.parquet"
        self.con.sql(f"COPY kcore_data TO '{full_data_path}' (FORMAT PARQUET);")
        logger.info("Chronological sequence saved to %s", full_data_path)

        catalog_path = f"{PROCESSED_PATH}/item_catalog.parquet"
        extract_catalog_query = f"""
        COPY (
            SELECT DISTINCT bundle_id, bundle_name, bundle_type, product_category,
                   service_class_category, price, validity, data_volume_mb, voice_volume_min, sms_volume_count
            FROM kcore_data
        ) TO '{catalog_path}' (FORMAT PARQUET);
        """
        self.con.sql(extract_catalog_query)
        logger.info("Item Catalog extracted and saved to %s", catalog_path)