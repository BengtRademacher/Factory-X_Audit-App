from typing import Mapping


OPERATING_STATES = ["Standby", "Ready", "E-Stop", "Processing", "Off"]

OPERATING_TO_MACHINE_STATE: Mapping[str, str] = {
    "Standby": "Idle",
    "Ready": "Idle",
    "E-Stop": "Idle",
    "Processing": "Cutting",
    "Off": "Maintenance",
}

MACHINE_TO_DEFAULT_OPERATING_STATE: Mapping[str, str] = {
    "Idle": "Standby",
    "Cutting": "Processing",
    "Cooling": "Ready",
    "Maintenance": "Off",
}


def operating_state_to_machine_state(operating_state: str) -> str:
    return OPERATING_TO_MACHINE_STATE.get(operating_state, "Idle")


def default_operating_state(machine_state: str | None) -> str:
    return MACHINE_TO_DEFAULT_OPERATING_STATE.get(machine_state or "", "Standby")
