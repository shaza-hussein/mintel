import os
import sys
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../..")))


SYSTEM_NAMES = (
    "SDP VAS",
    "MTN ME2U",
    "MTN Xtratime",
    "MTN Call Me Back",
    "MTN Tv",
)

RAW_REQUIRED_COLUMNS = (
    "configured_volume",
    "price",
    "validity",
    "bundle_name",
    "week_number",
)

RAW_TARGET_REQUIRED_COLUMNS = (
    "total_rev",
    "unique_users",
    "usage_type",
)

FEATURE_ENGINEERING_REQUIRED_COLUMNS = (
    "bundle_name",
    "week_number",
    "price",
    "configured_volume_mb",
    "configured_volume_min",
    "configured_volume_sms",
    "validity_hours",
    "is_illimite",
)

CATEGORICAL_FEATURE_COLUMNS = (
    "season",
    "bundle_type",
    "usage_type",
    "service_class_category",
    "validity_bucket",
)

MODEL_BASE_FEATURE_COLUMNS = (
    "week_number",
    "season",
    "week_sin",
    "week_cos",
    "bundle_type",
    "price",
    "usage_type",
    "service_class_category",
    "log_price",
    "volume_mb",
    "volume_min",
    "volume_sms",
    "log_mb",
    "log_min",
    "log_sms",
    "validity_hours",
    "validity_days",
    "log_validity_hours",
    "validity_bucket",
    "has_data",
    "has_voice",
    "has_sms",
    "is_data_only",
    "is_voice_only",
    "is_sms_only",
    "is_combo_bundle",
    "is_unlimited_bundle",
    "name_has_social",
    "name_has_roaming",
)
