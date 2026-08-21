import os
import logging
import duckdb

# Setup Logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("eSASRec.Pipeline")

# Paths
BASE_PATH = os.path.expanduser('~/secure_data')
DATA_PATH = f"{BASE_PATH}/**/*.parquet"
PROCESSED_PATH = os.path.expanduser('~/processed_data')

# DuckDB Configurations
DUCK_TEMP_DIR = "/tmp/duckdb_spill"
DUCK_TEMP_MICRO = "/tmp/duckdb_spill_micro"

# Pipeline Settings
COLUMNS_TO_EXCLUDE = "usage_type, volume, call_duration, dynamic_speed, gender, date_of_birth"
CUTOFF_DATE = 20251101
CHUNK_SIZE = 50000

def get_db_connection(micro_mode=False):
    """Returns a configured DuckDB connection."""
    os.makedirs(PROCESSED_PATH, exist_ok=True)
    con = duckdb.connect()
    
    if micro_mode:
        os.makedirs(DUCK_TEMP_MICRO, exist_ok=True)
        con.execute(f"PRAGMA temp_directory='{DUCK_TEMP_MICRO}'")
        con.execute("PRAGMA memory_limit='2GB'")
        con.execute("PRAGMA threads=1")
    else:
        os.makedirs(DUCK_TEMP_DIR, exist_ok=True)
        con.execute(f"SET temp_directory='{DUCK_TEMP_DIR}'")
        con.execute("SET memory_limit='7GB'")
        
    return con