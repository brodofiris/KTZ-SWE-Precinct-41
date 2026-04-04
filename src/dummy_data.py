# Train data generator

import json
import time
import random
from datetime import datetime, timezone
from collections import deque

class TrainSimulator:
    def __init__(self):
        # 1 minute of rolling data
        self.history = deque(maxlen=60)
        
        # Timing and State
        self.tick_count = 0
        self.active_alert = "NORMAL"
        self.broken_sensor = None
        
        self.alert_types = [
            "ENGINE_OVERHEAT", 
            "CATASTROPHIC_FUEL_LEAK", 
            "TRACTION_SHORT_CIRCUIT", 
            "PNEUMATIC_PRESSURE_LOSS"
        ]
        
        # Mapping of (Category, Sensor_Key) so we can easily break them in the JSON
        self.sensor_keys = [
            ("kinematics", "speed_kmh"),
            ("environment", "outside_temperature_c"),
            ("engine_and_fuel", "engine_temperature_c"),
            ("engine_and_fuel", "fuel_level_liters"),
            ("pneumatics", "main_reservoir_psi"),
            ("electrical", "traction_voltage_v")
        ]
        
        self.reset_baselines()
        
        # Distances and fuel start once and persist
        self.fuel_liters = 15000.0  
        self.dist_next_stop_km = 45.0
        self.dist_final_stop_km = 850.0

    def reset_baselines(self):
        """Resets the volatile systems back to normal operating parameters."""
        self.speed_kmh = 110.0
        self.engine_temp_c = 90.0
        self.outside_temp_c = 15.0
        self.cabin_temp_c = 22.0
        self.main_reservoir_psi = 135.0  
        self.brake_pipe_psi = 90.0       
        self.traction_voltage = 800.0
        self.traction_amps = 1200.0
        self.hep_voltage = 480.0         
        self.hep_kw_draw = 350.0         

    def random_walk(self, current, min_val, max_val, max_step):
        step = random.uniform(-max_step, max_step)
        new_val = current + step
        return max(min_val, min(max_val, new_val))

    def generate_reading(self):
        # --- CYCLE MANAGEMENT (60s Normal, 15s Emergency, 5s Dead Sensor) = 80s Total ---
        cycle_position = self.tick_count % 45
        
        if cycle_position == 0:
            self.active_alert = "NORMAL"
            self.broken_sensor = None # Fix the broken sensor
            self.reset_baselines()
        elif cycle_position == 30:
            self.active_alert = random.choice(self.alert_types)
            print(f"\n[!] ALERT TRIGGERED: {self.active_alert}")
        elif cycle_position == 40:
            # Emergency is over, but it fried a sensor
            self.active_alert = "SENSOR_FAILURE"
            self.broken_sensor = random.choice(self.sensor_keys)
            print(f"\n[!] SENSOR DEAD: {self.broken_sensor[1]} went offline!")
            
        self.tick_count += 1

        # --- DISTANCE & BASE FUEL MATH ---
        distance_covered = self.speed_kmh / 3600
        self.dist_next_stop_km = max(0, self.dist_next_stop_km - distance_covered)
        self.dist_final_stop_km = max(0, self.dist_final_stop_km - distance_covered)
        fuel_burn_rate = (self.traction_amps / 1000) * 0.5 

        # --- NORMAL RANDOM WALK ---
        self.speed_kmh = self.random_walk(self.speed_kmh, 0, 160, 0.5)
        self.engine_temp_c = self.random_walk(self.engine_temp_c, 75, 105, 0.2)
        self.outside_temp_c = self.random_walk(self.outside_temp_c, -20, 40, 0.05)
        self.cabin_temp_c = self.random_walk(self.cabin_temp_c, 20, 24, 0.02)
        self.main_reservoir_psi = self.random_walk(self.main_reservoir_psi, 125, 145, 1.0)
        self.brake_pipe_psi = self.random_walk(self.brake_pipe_psi, 88, 92, 0.1)
        self.traction_voltage = self.random_walk(self.traction_voltage, 500, 1000, 15.0)
        self.traction_amps = self.random_walk(self.traction_amps, 500, 1500, 25.0) 
        self.hep_voltage = self.random_walk(self.hep_voltage, 475, 485, 0.5)
        self.hep_kw_draw = self.random_walk(self.hep_kw_draw, 200, 500, 5.0)

        # --- APPLY EMERGENCY CHAOS MODIFIERS (Only runs during ticks 60-74) ---
        if self.active_alert == "ENGINE_OVERHEAT":
            self.engine_temp_c += random.uniform(1.5, 4.0) 
        elif self.active_alert == "CATASTROPHIC_FUEL_LEAK":
            leak_rate = random.uniform(15.0, 40.0)
            self.fuel_liters = max(0, self.fuel_liters - leak_rate)
            fuel_burn_rate += leak_rate 
        elif self.active_alert == "TRACTION_SHORT_CIRCUIT":
            self.traction_voltage = self.random_walk(self.traction_voltage, 0, 100, 150.0)
            self.traction_amps = self.random_walk(self.traction_amps, 0, 50, 300.0)
            self.speed_kmh -= random.uniform(1.0, 3.0) 
        elif self.active_alert == "PNEUMATIC_PRESSURE_LOSS":
            self.main_reservoir_psi -= random.uniform(3.0, 8.0)
            self.brake_pipe_psi -= random.uniform(2.0, 6.0)

        self.fuel_liters = max(0, self.fuel_liters - fuel_burn_rate)

        # --- COMPILE PAYLOAD ---
        reading = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "status": {
                "system_alert_state": self.active_alert
            },
            "kinematics": {
                "speed_kmh": round(self.speed_kmh, 2),
                "distance_to_next_stop_km": round(self.dist_next_stop_km, 2),
                "distance_to_final_stop_km": round(self.dist_final_stop_km, 2)
            },
            "environment": {
                "outside_temperature_c": round(self.outside_temp_c, 1),
                "cabin_temperature_c": round(self.cabin_temp_c, 1)
            },
            "engine_and_fuel": {
                "engine_temperature_c": round(self.engine_temp_c, 1),
                "fuel_level_liters": round(self.fuel_liters, 2),
                "fuel_burn_rate_lps": round(fuel_burn_rate, 3)
            },
            "pneumatics": {
                "main_reservoir_psi": round(self.main_reservoir_psi, 1),
                "brake_pipe_psi": round(self.brake_pipe_psi, 1)
            },
            "electrical": {
                "traction_voltage_v": round(self.traction_voltage, 1),
                "traction_current_a": round(self.traction_amps, 1),
                "head_end_power_voltage_v": round(self.hep_voltage, 1),
                "head_end_power_load_kw": round(self.hep_kw_draw, 1)
            }
        }

        # --- BREAK THE SENSOR IF NECESSARY ---
        # This will overwrite the specific sensor's value with `None` (which becomes `null` in JSON)
        if self.broken_sensor:
            category, sensor_name = self.broken_sensor
            reading[category][sensor_name] = None

        return reading

    def start(self, output_file="train_telemetry.json"):
        print(f"Starting Ultimate Train Data Simulator. Writing to {output_file}...")
        print("Cycle: 30s NORMAL -> 10s EMERGENCY -> 5s DEAD SENSOR. Press Ctrl+C to stop.")
        
        try:
            while True:
                new_data = self.generate_reading()
                self.history.append(new_data)
                
                with open(output_file, 'w') as f:
                    json.dump(list(self.history), f, indent=2)
                
                if self.active_alert not in ["NORMAL", "SENSOR_FAILURE"]:
                    print(f"CHAOS ACTIVE! Alert: {self.active_alert} | Speed: {new_data['kinematics']['speed_kmh']} | Temp: {new_data['engine_and_fuel']['engine_temperature_c']}")
                elif self.active_alert == "SENSOR_FAILURE" and self.broken_sensor is not None:
                    print(f"SENSOR OFFLINE: Transmitting null for {self.broken_sensor[1]}")

                time.sleep(1)
                
        except KeyboardInterrupt:
            print("\nSimulation stopped.")

if __name__ == "__main__":
    simulator = TrainSimulator()
    simulator.start()