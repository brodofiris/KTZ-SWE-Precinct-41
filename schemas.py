from pydantic import BaseModel
from datetime import datetime
from typing import Optional

class Status(BaseModel):
    system_alert_state: str

class Kinematics(BaseModel):
    speed_kmh: Optional[float] = None
    distance_to_next_stop_km: Optional[float] = None
    distance_to_final_stop_km: Optional[float] = None

class Environment(BaseModel):
    outside_temperature_c: Optional[float] = None
    cabin_temperature_c: Optional[float] = None

class EngineAndFuel(BaseModel):
    engine_temperature_c: Optional[float] = None
    fuel_level_liters: Optional[float] = None
    fuel_burn_rate_lps: Optional[float] = None

class Pneumatics(BaseModel):
    main_reservoir_psi: Optional[float] = None
    brake_pipe_psi: Optional[float] = None

class Electrical(BaseModel):
    traction_voltage_v: Optional[float] = None
    traction_current_a: Optional[float] = None
    head_end_power_voltage_v: Optional[float] = None
    head_end_power_load_kw: Optional[float] = None

class TelemetryEntry(BaseModel):
    timestamp: datetime
    status: Status
    kinematics: Kinematics
    environment: Environment
    engine_and_fuel: EngineAndFuel
    pneumatics: Pneumatics
    electrical: Electrical