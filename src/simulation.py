import random
import threading
import time
from dataclasses import dataclass
from typing import Dict, Optional


@dataclass(frozen=True)
class SimulatedSensor:
    id: str
    name: str


class SimulatedHeating:
    def __init__(self, update_interval=3.0, buffer_interval=0.3):
        self.heater0 = False
        self.heater1 = False
        self.heater0_output = False
        self.heater1_output = False
        self.swap_interval = update_interval
        self.swap_buffer_interval = buffer_interval
        self._running = False
        self._thread = None
        self._lock = threading.Lock()

    def _set_outputs(self, heater0_output, heater1_output):
        with self._lock:
            self.heater0_output = heater0_output
            self.heater1_output = heater1_output

    def get_output_states(self):
        with self._lock:
            return self.heater0_output, self.heater1_output

    def _run(self):
        toggle = False
        try:
            while self._running:
                if self.heater0 and self.heater1:
                    self._set_outputs(False, False)
                    time.sleep(self.swap_buffer_interval)

                    toggle = not toggle
                    if toggle:
                        self._set_outputs(True, False)
                    else:
                        self._set_outputs(False, True)

                    time.sleep(self.swap_interval)
                else:
                    self._set_outputs(self.heater0, self.heater1)
                    time.sleep(self.swap_interval)
        finally:
            self._set_outputs(False, False)

    def start(self):
        if not self._running:
            self._running = True
            self._thread = threading.Thread(target=self._run, daemon=True)
            self._thread.start()

    def stop(self):
        self._running = False
        if self._thread is not None:
            self._thread.join()
            self._thread = None
        self._set_outputs(False, False)


class SimulatedThermometers:
    offsets = {
        "sim_wort": 0.0,
        "sim_jacket": 0.0,
    }

    def __init__(self, heating_system, simulation_config=None):
        simulation_config = simulation_config or {}
        self.heating_system = heating_system
        self.update_interval = simulation_config.get("update_interval", 0.3)
        self.ambient_temp = simulation_config.get("ambient_temp", 20.0)
        self.heater_gain = simulation_config.get("heater_gain", 2.4)
        self.jacket_cooling = simulation_config.get("jacket_cooling", 0.035)
        self.wort_cooling = simulation_config.get("wort_cooling", 0.006)
        self.transfer_rate = simulation_config.get("transfer_rate", 0.08)
        self.wort_sensor_lag = simulation_config.get("wort_sensor_lag", 0.18)
        self.jacket_sensor_lag = simulation_config.get("jacket_sensor_lag", 0.35)
        self.noise_amplitude = simulation_config.get("noise_amplitude", 0.04)

        self.sensors = [
            SimulatedSensor("sim_wort", "Wort"),
            SimulatedSensor("sim_jacket", "Jacket"),
        ]
        self.temperatures: Dict[str, Optional[float]] = {
            sensor.id: None for sensor in self.sensors
        }

        self._wort_temp = simulation_config.get("initial_wort_temp", 21.5)
        self._jacket_temp = simulation_config.get("initial_jacket_temp", 21.0)
        self._wort_sensor_temp = self._wort_temp
        self._jacket_sensor_temp = self._jacket_temp
        self._running = False
        self._thread = None

    def _step_physics(self):
        heater0_output, heater1_output = self.heating_system.get_output_states()
        heater_power = float(heater0_output) + float(heater1_output)

        heat_to_wort = self.transfer_rate * (self._jacket_temp - self._wort_temp)
        jacket_loss = self.jacket_cooling * (self._jacket_temp - self.ambient_temp)
        wort_loss = self.wort_cooling * (self._wort_temp - self.ambient_temp)

        self._jacket_temp += (
            (self.heater_gain * heater_power) - heat_to_wort - jacket_loss
        ) * self.update_interval
        self._wort_temp += (heat_to_wort - wort_loss) * self.update_interval

        self._wort_sensor_temp += (
            self._wort_temp - self._wort_sensor_temp
        ) * self.wort_sensor_lag
        self._jacket_sensor_temp += (
            self._jacket_temp - self._jacket_sensor_temp
        ) * self.jacket_sensor_lag

        self.temperatures["sim_wort"] = (
            self._wort_sensor_temp
            + self.offsets["sim_wort"]
            + random.uniform(-self.noise_amplitude, self.noise_amplitude)
        )
        self.temperatures["sim_jacket"] = (
            self._jacket_sensor_temp
            + self.offsets["sim_jacket"]
            + random.uniform(-self.noise_amplitude, self.noise_amplitude)
        )

    def _update_loop(self):
        while self._running:
            self._step_physics()
            time.sleep(self.update_interval)

    def start(self):
        if not self._running:
            self._running = True
            self._thread = threading.Thread(target=self._update_loop, daemon=True)
            self._thread.start()

    def stop(self):
        self._running = False
        if self._thread is not None:
            self._thread.join()
            self._thread = None

    def get_temperature(self, sensor_id):
        return self.temperatures.get(sensor_id, None)
