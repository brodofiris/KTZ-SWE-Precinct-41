import json
import asyncio
import aiofiles
from schemas import TelemetryEntry
from database import init_db, insert_telemetry, cleanup_old_data

class TelemetryIngester:
    def __init__(self, filepath: str):
        self.filepath = filepath
        self.last_timestamp = None
        self.last_error = "None"

    async def get_latest_entry(self) -> TelemetryEntry | None:
        try:
            async with aiofiles.open(self.filepath, mode='r') as f:
                content = await f.read()
                data = json.loads(content)
                
                if not data:
                    return None
                
                latest_raw = data[-1] 
                self.last_error = "None" # Clear errors on success
                return TelemetryEntry(**latest_raw)
                
        except json.JSONDecodeError:
            self.last_error = "File locked/mid-write. Retrying..."
            return None
        except Exception as e:
            self.last_error = f"Error: {e}"
            return None

    async def start_watching(self, callback_func):
        while True:
            latest_entry = await self.get_latest_entry()
            
            # Update if we have new data OR if we need to show a new error on screen
            if latest_entry and latest_entry.timestamp != self.last_timestamp:
                self.last_timestamp = latest_entry.timestamp
                await callback_func(latest_entry, self.last_error)
            elif self.last_error != "None":
                await callback_func(latest_entry, self.last_error)
                
            await asyncio.sleep(1)

# --- Quick Test Block ---
def clear_console():
    """Uses ANSI escape codes to clear the screen instantly and cleanly."""
    print('\033[2J\033[H', end='')

# Add a global counter near the top of the file or above the callback
cleanup_counter = 0

async def database_and_cli_callback(data: TelemetryEntry, error_msg: str):
    global cleanup_counter
    
    # 1. Write to the Database
    if data:
        try:
            await insert_telemetry(data)
            
            # Run cleanup every 60 inserts (1 minute)
            cleanup_counter += 1
            if cleanup_counter >= 60:
                await cleanup_old_data()
                cleanup_counter = 0
                
        except Exception as e:
            error_msg = f"DB Write Error: {e}"

    # 2. Update the CLI (Same as before)
    clear_console()
    print("=" * 45)
    print(" 🚆 LIVE TRAIN TELEMETRY (CLI PROTOTYPE) 🚆")
    print("=" * 45)
    
    if data:
        print(f" Timestamp:  {data.timestamp.strftime('%Y-%m-%d %H:%M:%S')}")
        alert = data.status.system_alert_state
        print(f" Status:     {'!!! ' + alert + ' !!!' if alert != 'NORMAL' else alert}")
        print("-" * 45)
        
        spd = data.kinematics.speed_kmh
        print(f" Speed:      {f'{spd:>8.2f} km/h' if spd is not None else ' OFFLINE'}")
        eng = data.engine_and_fuel.engine_temperature_c
        print(f" Engine Temp:{f'{eng:>8.1f} °C' if eng is not None else ' OFFLINE'}")
        fuel = data.engine_and_fuel.fuel_level_liters
        print(f" Fuel Level: {f'{fuel:>8.2f} L' if fuel is not None else ' OFFLINE'}")
        
        tr_v = data.electrical.traction_voltage_v
        tr_a = data.electrical.traction_current_a
        v_str = f"{tr_v:>8.1f} V" if tr_v is not None else "OFFLINE"
        a_str = f"{tr_a:.1f} A" if tr_a is not None else "OFFLINE"
        print(f" Traction:   {v_str} | {a_str}")
        
    print("=" * 45)
    print(f" System Log: {error_msg}")

# And update the __main__ block to initialize the DB first
if __name__ == "__main__":
    # Initialize the database tables before starting the ingester
    asyncio.run(init_db())
    
    ingester = TelemetryIngester("train_telemetry.json")
    # Make sure to pass the updated callback name!
    asyncio.run(ingester.start_watching(database_and_cli_callback))