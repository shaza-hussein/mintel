import os
import sys
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../../..")))
import glob
import json
import logging
from pathlib import Path
from typing import Optional

import duckdb

from src.app.customers.targeting.graphSAGE.config import GraphBuildConfig
from src.app.customers.targeting.graphSAGE.contracts import GraphBuildResult

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(name)s | %(message)s")


def _sql_path(path: Path) -> str:
    return str(path).replace("\\", "/").replace("'", "''")


class GraphSAGEGraphBuilder:
    def __init__(self, config: Optional[GraphBuildConfig] = None) -> None:
        self.config = config or GraphBuildConfig()

    def build(self) -> GraphBuildResult:
        self.config.graph_dir.mkdir(parents=True, exist_ok=True)
        self.config.duckdb_temp_dir.mkdir(parents=True, exist_ok=True)

        parquet_files = sorted(
            set(glob.glob(str(self.config.input_parquet_dir / self.config.parquet_glob)))
        )
        if not parquet_files:
            raise FileNotFoundError(f"No parquet files found in {self.config.input_parquet_dir}")

        logger.info("Found parquet chunks | count=%d", len(parquet_files))

        con = duckdb.connect(str(self.config.db_path))
        con.execute(f"PRAGMA threads={self.config.duckdb_threads}")
        con.execute(f"PRAGMA temp_directory='{_sql_path(self.config.duckdb_temp_dir)}'")

        raw_rel = con.read_parquet(parquet_files, union_by_name=True)
        raw_rel.create_view("raw_in")

        self._create_raw_view(con)
        self._build_user_nodes(con)
        self._build_bundle_nodes(con)
        self._build_edges(con)
        metrics = self._collect_metrics(con)
        self._save_parquets(con)
        self._save_metrics(metrics)

        con.close()
        return GraphBuildResult(graph_dir=self.config.graph_dir, metrics=metrics)

    def _create_raw_view(self, con) -> None:
        con.execute("""
        CREATE OR REPLACE VIEW raw AS
        SELECT
            CAST(tbl_dt AS INTEGER) AS tbl_dt,
            CAST(msisdn AS VARCHAR) AS msisdn,
            CAST(bundle_id AS VARCHAR) AS bundle_id,
            CAST(bundle_name AS VARCHAR) AS bundle_name,
            CAST(bundle_type AS VARCHAR) AS bundle_type,
            CAST(price AS DOUBLE) AS price,
            CAST(subscriptions AS DOUBLE) AS subscriptions,
            CAST(total_rev AS DOUBLE) AS total_rev,
            CAST(service_class_category AS VARCHAR) AS service_class_category,
            CAST(canal AS VARCHAR) AS canal,
            CAST(payment_mode AS VARCHAR) AS payment_mode,
            CAST(department_city AS VARCHAR) AS department_city,
            CAST(brand_name AS VARCHAR) AS brand_name,
            CAST(device_capability AS VARCHAR) AS device_capability,
            CAST(configured_volume_mb AS DOUBLE) AS configured_volume_mb,
            CAST(configured_volume_min AS DOUBLE) AS configured_volume_min,
            CAST(configured_volume_sms AS DOUBLE) AS configured_volume_sms,
            CAST(validity_hours AS DOUBLE) AS validity_hours
        FROM raw_in
        WHERE msisdn IS NOT NULL
          AND bundle_id IS NOT NULL
          AND tbl_dt IS NOT NULL
        """)

    def _build_user_nodes(self, con) -> None:
        train_end = self.config.train_end_dt
        con.execute(f"""
        CREATE OR REPLACE TABLE user_nodes_train AS
        WITH user_agg AS (
            SELECT
                msisdn,
                COUNT(*) AS raw_events,
                COUNT(DISTINCT tbl_dt) AS active_days,
                COUNT(DISTINCT bundle_id) AS distinct_bundles,
                SUM(COALESCE(subscriptions, 0)) AS total_subscriptions,
                SUM(COALESCE(total_rev, 0)) AS total_revenue,
                AVG(COALESCE(price, 0)) AS avg_price,
                MAX(COALESCE(price, 0)) AS max_price,
                SUM(CASE WHEN bundle_type = 'BUNDLE_DATA' THEN COALESCE(subscriptions, 0) ELSE 0 END) AS subs_data,
                SUM(CASE WHEN bundle_type = 'BUNDLE_VOICE' THEN COALESCE(subscriptions, 0) ELSE 0 END) AS subs_voice,
                SUM(CASE WHEN bundle_type = 'BUNDLE_SMS' THEN COALESCE(subscriptions, 0) ELSE 0 END) AS subs_sms,
                MAX(tbl_dt) AS last_seen_tbl_dt,
                COALESCE(ARG_MAX(service_class_category, tbl_dt), 'UNK') AS service_class_category,
                COALESCE(ARG_MAX(canal, tbl_dt), 'UNK') AS canal,
                COALESCE(ARG_MAX(payment_mode, tbl_dt), 'UNK') AS payment_mode,
                COALESCE(ARG_MAX(department_city, tbl_dt), 'UNK') AS department_city,
                COALESCE(ARG_MAX(brand_name, tbl_dt), 'UNK') AS brand_name,
                COALESCE(ARG_MAX(device_capability, tbl_dt), 'UNK') AS device_capability
            FROM raw
            WHERE tbl_dt <= {train_end}
            GROUP BY msisdn
        )
        SELECT ROW_NUMBER() OVER (ORDER BY msisdn) - 1 AS user_idx, *
        FROM user_agg
        """)

    def _build_bundle_nodes(self, con) -> None:
        train_end = self.config.train_end_dt
        con.execute(f"""
        CREATE OR REPLACE TABLE bundle_nodes_train AS
        WITH bundle_agg AS (
            SELECT
                bundle_id,
                COALESCE(ARG_MAX(bundle_name, tbl_dt), 'UNK') AS bundle_name,
                COALESCE(ARG_MAX(bundle_type, tbl_dt), 'UNK') AS bundle_type,
                COALESCE(ARG_MAX(price, tbl_dt), 0) AS price,
                AVG(COALESCE(configured_volume_mb, 0)) AS configured_volume_mb,
                AVG(COALESCE(configured_volume_min, 0)) AS configured_volume_min,
                AVG(COALESCE(configured_volume_sms, 0)) AS configured_volume_sms,
                AVG(COALESCE(validity_hours, 0)) AS validity_hours,
                COUNT(*) AS raw_events,
                COUNT(DISTINCT msisdn) AS distinct_users,
                SUM(COALESCE(subscriptions, 0)) AS total_subscriptions,
                SUM(COALESCE(total_rev, 0)) AS total_revenue,
                MIN(tbl_dt) AS first_seen_tbl_dt,
                MAX(tbl_dt) AS last_seen_tbl_dt
            FROM raw
            WHERE tbl_dt <= {train_end}
            GROUP BY bundle_id
        )
        SELECT ROW_NUMBER() OVER (ORDER BY bundle_id) - 1 AS bundle_idx, *
        FROM bundle_agg
        """)

    def _build_edges(self, con) -> None:
        self._build_split_edges(con, "train_edges", f"tbl_dt <= {self.config.train_end_dt}")
        self._build_split_edges(
            con,
            "val_edges",
            f"tbl_dt > {self.config.train_end_dt} AND tbl_dt <= {self.config.val_end_dt}",
        )
        self._build_split_edges(con, "test_edges", f"tbl_dt > {self.config.val_end_dt}")

    def _build_split_edges(self, con, table_name: str, where_clause: str) -> None:
        con.execute(f"""
        CREATE OR REPLACE TABLE {table_name} AS
        WITH edge_agg AS (
            SELECT
                msisdn,
                bundle_id,
                COUNT(*) AS raw_events,
                COUNT(DISTINCT tbl_dt) AS active_days,
                SUM(COALESCE(subscriptions, 0)) AS total_subscriptions,
                SUM(COALESCE(total_rev, 0)) AS total_revenue,
                COALESCE(ARG_MAX(price, tbl_dt), 0) AS price,
                MIN(tbl_dt) AS first_tbl_dt,
                MAX(tbl_dt) AS last_tbl_dt
            FROM raw
            WHERE {where_clause}
            GROUP BY msisdn, bundle_id
        )
        SELECT
            u.user_idx,
            b.bundle_idx,
            e.msisdn,
            e.bundle_id,
            e.raw_events,
            e.active_days,
            e.total_subscriptions,
            e.total_revenue,
            e.price,
            e.first_tbl_dt,
            e.last_tbl_dt
        FROM edge_agg e
        JOIN user_nodes_train u ON e.msisdn = u.msisdn
        JOIN bundle_nodes_train b ON e.bundle_id = b.bundle_id
        """)

    def _collect_metrics(self, con) -> dict:
        graph_size = con.execute("""
        SELECT
            (SELECT COUNT(*) FROM user_nodes_train) AS train_user_nodes,
            (SELECT COUNT(*) FROM bundle_nodes_train) AS train_bundle_nodes,
            (SELECT COUNT(*) FROM train_edges) AS train_edges,
            (SELECT COUNT(*) FROM val_edges) AS val_edges,
            (SELECT COUNT(*) FROM test_edges) AS test_edges
        """).df().iloc[0].to_dict()

        sparsity = con.execute("""
        WITH s AS (
            SELECT
                (SELECT COUNT(*) FROM user_nodes_train) AS num_users,
                (SELECT COUNT(*) FROM bundle_nodes_train) AS num_bundles,
                (SELECT COUNT(*) FROM train_edges) AS num_edges
        )
        SELECT
            num_users,
            num_bundles,
            num_edges,
            num_users * num_bundles AS possible_edges,
            num_edges * 1.0 / NULLIF(num_users * num_bundles, 0) AS graph_density
        FROM s
        """).df().iloc[0].to_dict()

        return {
            "graph_size": graph_size,
            "train_sparsity": sparsity,
            "train_end_dt": self.config.train_end_dt,
            "val_end_dt": self.config.val_end_dt,
        }

    def _save_parquets(self, con) -> None:
        for table in [
            "user_nodes_train",
            "bundle_nodes_train",
            "train_edges",
            "val_edges",
            "test_edges",
        ]:
            path = self.config.graph_dir / f"{table}.parquet"
            con.execute(f"COPY {table} TO '{_sql_path(path)}' (FORMAT PARQUET)")
            logger.info("Saved graph table | table=%s | path=%s", table, path)

    def _save_metrics(self, metrics: dict) -> None:
        path = self.config.graph_dir / "graph_build_metrics.json"
        with path.open("w", encoding="utf-8") as file:
            json.dump(metrics, file, indent=4, default=str)


def build_graphsage_graph(config: Optional[GraphBuildConfig] = None) -> GraphBuildResult:
    return GraphSAGEGraphBuilder(config=config).build()