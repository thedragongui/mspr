from __future__ import annotations

from typing import Any

import pandas as pd


ELECTION_RATIO_COLUMNS = [
    "share_winner",
    "extreme_gauche",
    "gauche",
    "centre",
    "droite",
    "extreme_droite",
    "droite_nat",
    "turnout_rate",
    "abstention_rate",
    "valid_ballot_rate",
    "invalid_ballot_rate",
    "municipal_turnout_rate_latest",
    "municipal_valid_ballot_rate_latest",
    "municipal_winner_share_latest",
]


def _as_int_years(df: pd.DataFrame) -> list[int]:
    if "year" not in df.columns or df.empty:
        return []
    years = pd.to_numeric(df["year"], errors="coerce").dropna().astype(int).tolist()
    return sorted(set(years))


def resolve_test_years(df: pd.DataFrame, requested_test_years: list[int] | None) -> list[int]:
    """
    Resolve test years against available years.
    If no test years are provided, keep only the latest available election year.
    """
    available_years = _as_int_years(df)
    if not available_years:
        raise RuntimeError("Aucune annee disponible dans le dataset ML.")

    if not requested_test_years:
        return [int(max(available_years))]

    requested = sorted(set(int(y) for y in requested_test_years))
    resolved = [int(y) for y in requested if y in set(available_years)]
    if not resolved:
        raise RuntimeError(
            "Aucune annee de test valide apres filtrage. "
            f"Annees disponibles={available_years}, demandees={requested}"
        )
    return resolved


def _safe_ratio(numerator: int, denominator: int) -> float:
    if denominator <= 0:
        return 0.0
    return float(numerator) / float(denominator)


def _key_columns(scope: str, df: pd.DataFrame) -> list[str]:
    keys = ["year"]
    if scope == "commune" and "geo_code" in df.columns:
        keys.append("geo_code")
    elif "dept_code" in df.columns:
        keys.append("dept_code")
    elif "geo_code" in df.columns:
        keys.append("geo_code")
    return keys


def assess_ml_dataset_quality(
    df: pd.DataFrame,
    target: str,
    scope: str,
    feature_columns: list[str] | None,
    test_years: list[int],
    null_warn_threshold: float = 0.95,
    target_missing_fail_threshold: float = 0.25,
) -> dict[str, Any]:
    """
    Lightweight quality gate for ML datasets.
    Returns a report with pass/fail + diagnostics.
    """
    if scope not in {"departement", "commune"}:
        raise ValueError(f"Invalid scope for quality checks: {scope}")

    available_years = _as_int_years(df)
    selected_test_years = sorted(set(int(y) for y in test_years))
    train_years = [int(y) for y in available_years if y not in set(selected_test_years)]

    key_cols = _key_columns(scope=scope, df=df)
    duplicate_key_rows = int(df.duplicated(subset=key_cols).sum()) if len(key_cols) > 1 else 0

    target_series = pd.to_numeric(df.get("target"), errors="coerce")
    target_non_null = target_series.notna()
    target_missing_rows = int((~target_non_null).sum())
    target_missing_ratio = _safe_ratio(target_missing_rows, int(len(df)))
    target_out_of_range_rows = int(((target_series < 0.0) | (target_series > 1.0)).fillna(False).sum())
    target_out_of_range_ratio = _safe_ratio(target_out_of_range_rows, int(target_non_null.sum()))

    # Election ratio integrity in [0, 1]
    rate_out_of_range: dict[str, dict[str, float | int]] = {}
    ratio_cols = list(dict.fromkeys(ELECTION_RATIO_COLUMNS + [f"{target}_prev", target]))
    for col in ratio_cols:
        if col not in df.columns:
            continue
        values = pd.to_numeric(df[col], errors="coerce")
        not_null = values.notna()
        out_count = int(((values < 0.0) | (values > 1.0)).fillna(False).sum())
        rate_out_of_range[col] = {
            "rows_out_of_range": out_count,
            "ratio_out_of_range": _safe_ratio(out_count, int(not_null.sum())),
        }

    # Basic election count constraints
    count_violations = {
        "votes_cast_gt_registered": 0,
        "votes_valid_gt_votes_cast": 0,
        "votes_gt_votes_valid": 0,
    }
    if {"registered", "votes_cast"}.issubset(df.columns):
        registered = pd.to_numeric(df["registered"], errors="coerce")
        votes_cast = pd.to_numeric(df["votes_cast"], errors="coerce")
        count_violations["votes_cast_gt_registered"] = int((votes_cast > registered).fillna(False).sum())
    if {"votes_cast", "votes_valid"}.issubset(df.columns):
        votes_cast = pd.to_numeric(df["votes_cast"], errors="coerce")
        votes_valid = pd.to_numeric(df["votes_valid"], errors="coerce")
        count_violations["votes_valid_gt_votes_cast"] = int((votes_valid > votes_cast).fillna(False).sum())
    if {"votes_valid", "votes"}.issubset(df.columns):
        votes_valid = pd.to_numeric(df["votes_valid"], errors="coerce")
        votes = pd.to_numeric(df["votes"], errors="coerce")
        count_violations["votes_gt_votes_valid"] = int((votes > votes_valid).fillna(False).sum())

    features = [c for c in (feature_columns or []) if c in df.columns]
    null_ratios = []
    constant_features: list[str] = []
    if features:
        feature_df = df[features].copy()
        null_ratio_series = feature_df.isna().mean().sort_values(ascending=False)
        null_ratios = [
            {"column": str(col), "null_ratio": float(ratio)}
            for col, ratio in null_ratio_series.head(30).items()
        ]
        constant_features = [
            str(col)
            for col in feature_df.columns
            if feature_df[col].dropna().nunique() <= 1
        ]

    high_null_features = [
        item["column"]
        for item in null_ratios
        if float(item["null_ratio"]) >= float(null_warn_threshold)
    ]

    train_rows = int(df[df["year"].isin(train_years)].shape[0]) if "year" in df.columns else 0
    test_rows = int(df[df["year"].isin(selected_test_years)].shape[0]) if "year" in df.columns else 0

    critical_issues: list[str] = []
    warning_issues: list[str] = []

    if df.empty:
        critical_issues.append("Dataset vide.")
    if not available_years:
        critical_issues.append("Aucune annee exploitable.")
    if train_rows <= 0:
        critical_issues.append("Aucune ligne d'entrainement apres selection des annees.")
    if test_rows <= 0:
        critical_issues.append("Aucune ligne de test pour l'annee cible.")
    if duplicate_key_rows > 0:
        critical_issues.append(f"{duplicate_key_rows} doublons detectes sur les cles {key_cols}.")
    if target_missing_ratio > float(target_missing_fail_threshold):
        critical_issues.append(
            f"Trop de cibles manquantes: {target_missing_rows}/{len(df)} "
            f"({target_missing_ratio:.1%})."
        )
    if target_out_of_range_rows > 0:
        critical_issues.append(
            f"Cible hors [0,1]: {target_out_of_range_rows} lignes ({target_out_of_range_ratio:.1%})."
        )

    for col, stats in rate_out_of_range.items():
        if int(stats["rows_out_of_range"]) > 0:
            critical_issues.append(
                f"Colonne {col}: {int(stats['rows_out_of_range'])} valeurs hors [0,1]."
            )

    for rule, count in count_violations.items():
        if int(count) > 0:
            critical_issues.append(f"Contrainte {rule} violee sur {int(count)} lignes.")

    if high_null_features:
        warning_issues.append(
            f"{len(high_null_features)} feature(s) ont >= {int(null_warn_threshold * 100)}% de valeurs nulles."
        )
    if constant_features:
        warning_issues.append(f"{len(constant_features)} feature(s) constantes detectees.")

    status = "fail" if critical_issues else "pass"
    report: dict[str, Any] = {
        "status": status,
        "scope": scope,
        "target": target,
        "row_count": int(len(df)),
        "available_years": available_years,
        "test_years": selected_test_years,
        "train_years": train_years,
        "train_rows": train_rows,
        "test_rows": test_rows,
        "key_columns": key_cols,
        "duplicate_key_rows": duplicate_key_rows,
        "target_missing_rows": target_missing_rows,
        "target_missing_ratio": target_missing_ratio,
        "target_out_of_range_rows": target_out_of_range_rows,
        "target_out_of_range_ratio": target_out_of_range_ratio,
        "rate_out_of_range": rate_out_of_range,
        "count_violations": count_violations,
        "feature_count_checked": int(len(features)),
        "high_null_features": high_null_features[:50],
        "high_null_feature_count": int(len(high_null_features)),
        "constant_features": constant_features[:50],
        "constant_feature_count": int(len(constant_features)),
        "top_feature_null_ratios": null_ratios,
        "critical_issues": critical_issues,
        "warning_issues": warning_issues,
    }
    return report
