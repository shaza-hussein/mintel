import os
import glob
import pandas as pd
from .config import logger, PROCESSED_PATH, CHUNK_SIZE, CUTOFF_DATE

class SequenceMaker:
    def __init__(self, con):
        self.con = con

    def build_indices(self):
        logger.info("Executing Dense Indexing...")
        kcore_file = f"{PROCESSED_PATH}/kcore_filtered_data.parquet"
        self.con.sql(f"CREATE OR REPLACE TABLE kcore_data AS SELECT * FROM read_parquet('{kcore_file}');")
        
        self.con.sql("""
        CREATE OR REPLACE TABLE user_map AS
        SELECT msisdn, ROW_NUMBER() OVER (ORDER BY msisdn) AS user_id
        FROM (SELECT DISTINCT msisdn FROM kcore_data);
        """)

        self.con.sql("""
        CREATE OR REPLACE TABLE item_map AS
        SELECT bundle_id, ROW_NUMBER() OVER (ORDER BY bundle_id) AS item_id
        FROM (SELECT DISTINCT bundle_id FROM kcore_data);
        """)

        self.con.sql("""
        CREATE OR REPLACE TABLE tokenized_data AS
        SELECT u.user_id, i.item_id, k.tbl_dt
        FROM kcore_data k
        JOIN user_map u ON k.msisdn = u.msisdn
        JOIN item_map i ON k.bundle_id = i.bundle_id
        ORDER BY u.user_id, k.tbl_dt;
        """)

        self.con.sql(f"COPY user_map TO '{PROCESSED_PATH}/user_mapping.parquet' (FORMAT PARQUET);")
        self.con.sql(f"COPY item_map TO '{PROCESSED_PATH}/item_mapping.parquet' (FORMAT PARQUET);")
        self.con.sql(f"COPY tokenized_data TO '{PROCESSED_PATH}/tokenized_data.parquet' (FORMAT PARQUET);")
        logger.info("Indexing complete and mapping files saved.")

    def execute_micro_chunking(self):
        logger.info("Activating Micro-Chunking processing protocol...")
        max_user_id = self.con.sql(f"SELECT MAX(user_id) FROM read_parquet('{PROCESSED_PATH}/tokenized_data.parquet')").fetchone()[0]
        
        for start_id in range(1, int(max_user_id) + 1, CHUNK_SIZE):
            end_id = start_id + CHUNK_SIZE - 1
            file_name = f"{PROCESSED_PATH}/user_sequences_part_{start_id}.parquet"
            
            if os.path.exists(file_name):
                logger.info("Chunk %d to %d exists, skipping.", start_id, end_id)
                continue
                
            chunk_query = f"""
            COPY (
                SELECT user_id,
                       LIST(item_id ORDER BY tbl_dt ASC) AS item_sequence,
                       LIST(tbl_dt ORDER BY tbl_dt ASC) AS date_sequence
                FROM read_parquet('{PROCESSED_PATH}/tokenized_data.parquet')
                WHERE user_id BETWEEN {start_id} AND {end_id}
                GROUP BY user_id
            ) TO '{file_name}' (FORMAT PARQUET);
            """
            self.con.sql(chunk_query)

        logger.info("Micro-partitioning complete. Merging sequences...")
        merge_query = f"""
        COPY (
            SELECT * FROM read_parquet('{PROCESSED_PATH}/user_sequences_part_*.parquet')
        ) TO '{PROCESSED_PATH}/user_sequences.parquet' (FORMAT PARQUET);
        """
        self.con.sql(merge_query)
        
        part_files = glob.glob(f"{PROCESSED_PATH}/user_sequences_part_*.parquet")
        for f in part_files: os.remove(f)
        logger.info("Temporary chunk files cleaned up.")

    def execute_temporal_split(self):
        logger.info("Starting Chronological Time-Split protocol...")
        file_path = f"{PROCESSED_PATH}/user_sequences.parquet"
        df = pd.read_parquet(file_path)

        def temporal_split(row):
            items, dates = row['item_sequence'], row['date_sequence']
            split_idx = len(dates)
            for i, d in enumerate(dates):
                if d >= CUTOFF_DATE:
                    split_idx = i
                    break
            return items[:split_idx], items[split_idx:]

        df[['train_sequence', 'test_sequence']] = df.apply(temporal_split, axis=1, result_type='expand')

        valid_users = df[
            (df['train_sequence'].apply(len) >= 2) & 
            (df['test_sequence'].apply(len) >= 1)
        ].copy()

        final_path = f"{PROCESSED_PATH}/pytorch_ready_data.parquet"
        valid_users[['user_id', 'train_sequence', 'test_sequence']].to_parquet(final_path, index=False)
        logger.info("Temporal split complete. PyTorch ready data saved to %s", final_path)