"""Digital Twin State management for COPD patient profiles.

Maintains patient identity, static baseline attributes, current visit state,
and full longitudinal visit history. Exclusively handles state storage and updates;
does not perform ML prediction or simulation.
"""

import copy
from typing import Any, Dict, List, Optional, Union
import pandas as pd


STATIC_FIELDS = [
    "sex",
    "age_at_baseline",
    "gold_stage_baseline",
    "smoking_status_baseline",
    "pack_years",
    "baseline_fev1_liters",
    "baseline_fvc_liters",
    "baseline_fev1_fvc_ratio",
    "bmi",
]


class TwinState:
    """Represents a digital twin state for a COPD patient.

    Properties
    ----------
    patient_id : str
        Unique identifier for the patient (e.g. 'P0001').
    static : Dict[str, Any]
        Fixed baseline fields establishing patient identity.
    current : Dict[str, Any]
        Most recent visit's observed and time-varying fields.
    history : List[Dict[str, Any]]
        Chronological list of all visits recorded for the patient.
    """

    def __init__(
        self,
        static_data: Dict[str, Any],
        initial_visit: Dict[str, Any],
        patient_id: Optional[str] = None,
    ) -> None:
        """Initialize the patient digital twin with static data and baseline visit.

        Parameters
        ----------
        static_data : Dict[str, Any]
            Static baseline fields (e.g. sex, pack_years, baseline FEV1).
        initial_visit : Dict[str, Any]
            Observation data for Visit 1.
        patient_id : Optional[str]
            Patient ID string. If not explicitly provided, extracted from
            static_data or initial_visit.
        """
        pid = (
            patient_id
            or static_data.get("patient_id")
            or initial_visit.get("patient_id")
        )
        if not pid:
            raise ValueError("A valid 'patient_id' must be provided in static_data, initial_visit, or explicitly.")

        self.patient_id: str = str(pid)
        self.static: Dict[str, Any] = copy.deepcopy(static_data)
        # Ensure patient_id is recorded in static data for consistency
        self.static["patient_id"] = self.patient_id

        init_visit_copy = copy.deepcopy(initial_visit)
        init_visit_copy["patient_id"] = self.patient_id

        self.history: List[Dict[str, Any]] = [init_visit_copy]
        self.current: Dict[str, Any] = init_visit_copy

    def add_visit(self, new_visit: Dict[str, Any]) -> None:
        """Append a new visit observation and update the current state.

        Parameters
        ----------
        new_visit : Dict[str, Any]
            New observation data (e.g. months_since_baseline, fev1_liters, etc.).
        """
        visit_copy = copy.deepcopy(new_visit)
        visit_copy["patient_id"] = self.patient_id
        self.history.append(visit_copy)
        self.current = visit_copy

    def to_dict(self) -> Dict[str, Any]:
        """Serialize twin state to a dictionary conforming to TwinStateResponse.

        Returns
        -------
        Dict[str, Any]
            Dictionary containing patient_id, static, current, and history.
        """
        return {
            "patient_id": self.patient_id,
            "static": copy.deepcopy(self.static),
            "current": copy.deepcopy(self.current),
            "history": copy.deepcopy(self.history),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "TwinState":
        """Reconstruct a TwinState instance from a serialized dictionary.

        Parameters
        ----------
        data : Dict[str, Any]
            Dictionary containing 'patient_id', 'static', and 'history' (or 'current').

        Returns
        -------
        TwinState
            Reconstructed TwinState instance.
        """
        patient_id = data.get("patient_id")
        static_data = data.get("static", {})
        history = data.get("history", [])

        if history:
            initial_visit = history[0]
            twin = cls(static_data=static_data, initial_visit=initial_visit, patient_id=patient_id)
            for v in history[1:]:
                twin.add_visit(v)
            return twin

        current = data.get("current", {})
        return cls(static_data=static_data, initial_visit=current, patient_id=patient_id)

    @classmethod
    def from_dataframe(cls, patient_df: pd.DataFrame) -> "TwinState":
        """Create a TwinState from a sorted DataFrame of visits for a single patient.

        Parameters
        ----------
        patient_df : pd.DataFrame
            Visits for one patient, sorted by visit_number or months_since_baseline.

        Returns
        -------
        TwinState
            Initialized TwinState with full visit history loaded.
        """
        if patient_df.empty:
            raise ValueError("Cannot initialize TwinState from an empty DataFrame.")

        unique_pids = patient_df["patient_id"].unique()
        if len(unique_pids) != 1:
            raise ValueError(f"DataFrame must contain records for exactly 1 patient, got: {unique_pids}")

        patient_id = str(unique_pids[0])
        sorted_df = patient_df.sort_values("visit_number").reset_index(drop=True)
        row0 = sorted_df.iloc[0].to_dict()

        # Extract static baseline fields
        static_data = {"patient_id": patient_id}
        for field in STATIC_FIELDS:
            if field in row0:
                static_data[field] = row0[field]
            elif field == "age_at_baseline" and "age_at_visit" in row0:
                static_data["age_at_baseline"] = row0["age_at_visit"]

        twin = cls(static_data=static_data, initial_visit=row0, patient_id=patient_id)

        for i in range(1, len(sorted_df)):
            twin.add_visit(sorted_df.iloc[i].to_dict())

        return twin

    def __repr__(self) -> str:
        return (
            f"TwinState(patient_id='{self.patient_id}', "
            f"visits={len(self.history)}, "
            f"latest_visit={self.current.get('visit_number', 'unknown')})"
        )
