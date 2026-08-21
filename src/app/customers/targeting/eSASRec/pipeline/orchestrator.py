from .config import get_db_connection, logger
from .cleaner import DataCleaner
from .kcore_filter import KCoreFilter
from .sequence_maker import SequenceMaker

def run_data_pipeline():
    logger.info("Initializing eSASRec Data Pipeline...")
    
    # Phase 1 & 2: Memory heavy operations
    con = get_db_connection(micro_mode=False)
    
    try:
        cleaner = DataCleaner(con)
        cleaner.execute_base_cleaning()
        cleaner.process_prices()
        cleaner.process_validity()
        cleaner.process_volumes()
        cleaner.finalize_schema()
        
        filter_engine = KCoreFilter(con)
        filter_engine.execute()
        filter_engine.export_checkpoints()
    finally:
        con.close()
        
    # Phase 3: Strict memory operations (Micro-chunking)
    con_micro = get_db_connection(micro_mode=True)
    try:
        seq_maker = SequenceMaker(con_micro)
        seq_maker.build_indices()
        seq_maker.execute_micro_chunking()
    finally:
        con_micro.close()

    # Phase 4: Time Splitting (Pandas based)
    dummy_con = None # Not needed for pandas ops
    seq_maker_pandas = SequenceMaker(dummy_con)
    seq_maker_pandas.execute_temporal_split()

    logger.info("Pipeline executed successfully! Data is ready for PyTorch.")

if __name__ == "__main__":
    run_data_pipeline()