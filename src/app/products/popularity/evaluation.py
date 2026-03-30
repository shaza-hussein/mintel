import os
import sys
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../..")))

import logging
from typing import Any

import numpy as np
import pandas as pd
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from src.app.products.popularity.contracts import EvaluationResult

import logging

logger = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s"
)

class RegressionEvaluator:
    
    @staticmethod
    def evaluate(
        model: Any,
        X_test: pd.DataFrame,
        y_test: pd.Series,
        return_predictions: bool = False,
    ) -> EvaluationResult:
        logger.info(
            "Starting regression evaluation | X_test_shape=%s | y_test_len=%d | return_predictions=%s",
            X_test.shape,
            len(y_test),
            return_predictions,
        )

        y_true = pd.Series(y_test).reset_index(drop=True).astype(float)
        y_pred = pd.Series(model.predict(X_test)).reset_index(drop=True).astype(float)

        mae = float(mean_absolute_error(y_true, y_pred))
        mse = float(mean_squared_error(y_true, y_pred))
        rmse = float(np.sqrt(mse))
        r2 = float(r2_score(y_true, y_pred))

        non_zero_mask = y_true != 0
        if non_zero_mask.sum() > 0:
            mape = float(
                np.abs((y_true[non_zero_mask] - y_pred[non_zero_mask]) / y_true[non_zero_mask]).mean()
                * 100
            )
        else:
            mape = None

        metrics = {
            "MAE": mae,
            "MSE": mse,
            "RMSE": rmse,
            "R2": r2,
            "MAPE_percent": mape,
        }

        logger.info(
            "Evaluation completed | MAE=%.6f | MSE=%.6f | RMSE=%.6f | R2=%.6f | MAPE_percent=%s",
            metrics["MAE"],
            metrics["MSE"],
            metrics["RMSE"],
            metrics["R2"],
            "None" if metrics["MAPE_percent"] is None else f"{metrics['MAPE_percent']:.6f}",
        )

        if return_predictions:
            predictions = pd.DataFrame(
                {
                    "actual": y_true,
                    "predicted": y_pred,
                    "abs_error": np.abs(y_true - y_pred),
                }
            )
            logger.info("Returning evaluation predictions | shape=%s", predictions.shape)
            return EvaluationResult(metrics=metrics, predictions=predictions)

        return EvaluationResult(metrics=metrics)
