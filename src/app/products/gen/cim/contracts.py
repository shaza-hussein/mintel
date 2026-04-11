import os
import sys
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../../..")))



class ExistingCols:
    ID            = "bundle_id"
    NAME          = "bundle_name"
    PRICE         = "price"
    VOLUME_MB     = "volume_mb"
    BUNDLE_TYPE   = "bundle_type"
    MINUTES       = "minutes"
    SMS           = "sms"
    AVG_REVENUE   = "avg_weekly_revenue"
    AVG_SUBS      = "avg_weekly_subs"
    POPULARITY    = "popularity_score"

class GeneratedCols:
    ID              = "bundle_id"
    BUNDLE_TYPE     = "bundle_type"
    USAGE_TYPE      = "usage_type"
    SERVICE_CLASS   = "service_class_category"
    PRICE           = "price"
    VOLUME_MB       = "volume_mb"
    VOLUME_MIN      = "volume_min"
    VOLUME_SMS      = "volume_sms"
    VALIDITY_HOURS  = "validity_hours"
    VALIDITY_DAYS   = "validity_days"
    VALIDITY_BUCKET = "validity_bucket"
    POPULARITY      = "predicted_popularity"
    POP_CATEGORY    = "popularity_category"

