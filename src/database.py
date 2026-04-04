import asyncio
from datetime import datetime, timedelta, timezone
from sqlalchemy import select, delete, Float, String, DateTime, desc, select, desc, Integer
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from typing import Optional

from src.schemas import TelemetryEntry



# SQLite connection string (async)
DATABASE_URL = "sqlite+aiosqlite:///./train_data.db"

engine = create_async_engine(DATABASE_URL, echo=False)
AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False)

# new telemetry
async def get_historical_telemetry(
    limit: int = 100, 
    start_date: Optional[datetime] = None, 
    end_date: Optional[datetime] = None
):
    """Fetches records, optionally filtered by a date range."""
    async with AsyncSessionLocal() as session:
        # Base query ordered by newest first
        query = select(TelemetryRecord).order_by(desc(TelemetryRecord.timestamp))
        
        # Apply filters conditionally if they are provided
        if start_date:
            query = query.where(TelemetryRecord.timestamp >= start_date)
        if end_date:
            query = query.where(TelemetryRecord.timestamp <= end_date)
            
        # Apply the limit at the end
        query = query.limit(limit)
        
        result = await session.execute(query)
        return result.scalars().all()

class Base(DeclarativeBase):
    pass

class TelemetryRecord(Base):
    __tablename__ = "telemetry_logs"

    # Primary Key
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    
    # Indexed timestamp for fast time-series graphing and cleanup
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    system_alert_state: Mapped[str] = mapped_column(String, default="NORMAL")

    # Kinematics (Nullable because sensors can break!)
    speed_kmh: Mapped[float | None] = mapped_column(Float, nullable=True)
    distance_to_next_stop_km: Mapped[float | None] = mapped_column(Float, nullable=True)
    distance_to_final_stop_km: Mapped[float | None] = mapped_column(Float, nullable=True)

    # Environment & Engine
    outside_temperature_c: Mapped[float | None] = mapped_column(Float, nullable=True)
    cabin_temperature_c: Mapped[float | None] = mapped_column(Float, nullable=True)
    engine_temperature_c: Mapped[float | None] = mapped_column(Float, nullable=True)
    fuel_level_liters: Mapped[float | None] = mapped_column(Float, nullable=True)
    fuel_burn_rate_lps: Mapped[float | None] = mapped_column(Float, nullable=True)

    # Pneumatics & Electrical
    main_reservoir_psi: Mapped[float | None] = mapped_column(Float, nullable=True)
    brake_pipe_psi: Mapped[float | None] = mapped_column(Float, nullable=True)
    traction_voltage_v: Mapped[float | None] = mapped_column(Float, nullable=True)
    traction_current_a: Mapped[float | None] = mapped_column(Float, nullable=True)
    head_end_power_voltage_v: Mapped[float | None] = mapped_column(Float, nullable=True)
    head_end_power_load_kw: Mapped[float | None] = mapped_column(Float, nullable=True)

async def init_db():
    """Creates the tables in the database."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    print("Database tables created successfully.")

async def insert_telemetry(data: TelemetryEntry):
    """Flattens the Pydantic schema and inserts it into the DB."""
    async with AsyncSessionLocal() as session:
        record = TelemetryRecord(
            timestamp=data.timestamp,
            system_alert_state=data.status.system_alert_state,
            speed_kmh=data.kinematics.speed_kmh,
            distance_to_next_stop_km=data.kinematics.distance_to_next_stop_km,
            distance_to_final_stop_km=data.kinematics.distance_to_final_stop_km,
            outside_temperature_c=data.environment.outside_temperature_c,
            cabin_temperature_c=data.environment.cabin_temperature_c,
            engine_temperature_c=data.engine_and_fuel.engine_temperature_c,
            fuel_level_liters=data.engine_and_fuel.fuel_level_liters,
            fuel_burn_rate_lps=data.engine_and_fuel.fuel_burn_rate_lps,
            main_reservoir_psi=data.pneumatics.main_reservoir_psi,
            brake_pipe_psi=data.pneumatics.brake_pipe_psi,
            traction_voltage_v=data.electrical.traction_voltage_v,
            traction_current_a=data.electrical.traction_current_a,
            head_end_power_voltage_v=data.electrical.head_end_power_voltage_v,
            head_end_power_load_kw=data.electrical.head_end_power_load_kw
        )
        session.add(record)
        await session.commit()

async def cleanup_old_data():
    """Deletes records older than 24 hours to save space."""
    async with AsyncSessionLocal() as session:
        cutoff_time = datetime.now(timezone.utc) - timedelta(hours=24)
        query = delete(TelemetryRecord).where(TelemetryRecord.timestamp < cutoff_time)
        await session.execute(query)
        await session.commit()

class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    first_name: Mapped[str] = mapped_column(String)
    last_name: Mapped[str] = mapped_column(String)
    operator_id: Mapped[str] = mapped_column(String, unique=True, index=True) 
    hashed_password: Mapped[str] = mapped_column(String)
    role: Mapped[str] = mapped_column(String, default="operator")