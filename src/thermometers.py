import threading
import time
from typing import Dict, List, Optional

from w1thermsensor import W1ThermSensor


class Thermometers:
    def __init__(self, update_interval=1.0, offsets=None):
        self.offsets = dict(offsets or {})
        self.sensors: Dict[str, W1ThermSensor] = {}
        self.temperatures: Dict[str, Optional[float]] = {}
        self._lock = threading.Lock()
        self._refresh_sensors(log_changes=True)

        self.update_interval = update_interval
        self._running = False
        self._thread = None

    def _refresh_sensors(self, log_changes=False):
        available_sensors = W1ThermSensor.get_available_sensors()
        sensor_map = {sensor.id: sensor for sensor in available_sensors}

        with self._lock:
            previous_ids = set(self.sensors.keys())
            current_ids = set(sensor_map.keys())
            added_ids = sorted(current_ids - previous_ids)
            removed_ids = sorted(previous_ids - current_ids)

            self.sensors = sensor_map
            self.temperatures = {
                sensor_id: self.temperatures.get(sensor_id)
                for sensor_id in sorted(current_ids)
            }

        if log_changes:
            print(f"Found {len(sensor_map)} sensors")
            for sensor_id in sorted(current_ids):
                print(sensor_id)
        else:
            for sensor_id in added_ids:
                print(f"Sensor connected: {sensor_id}")
            for sensor_id in removed_ids:
                print(f"Sensor disconnected: {sensor_id}")

    def get_sensor_ids(self) -> List[str]:
        with self._lock:
            return list(self.temperatures.keys())

    def _update_loop(self):
        while self._running:
            self._refresh_sensors()

            with self._lock:
                sensors = list(self.sensors.items())

            for sensor_id, sensor in sensors:
                try:
                    temperature = sensor.get_temperature() + self.offsets.get(sensor_id, 0.0)
                    with self._lock:
                        self.temperatures[sensor_id] = temperature
                except Exception as e:
                    print(f"Error reading sensor {sensor_id}: {e}")
                    with self._lock:
                        if sensor_id in self.temperatures:
                            self.temperatures[sensor_id] = None

            with self._lock:
                print(dict(self.temperatures))
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
        with self._lock:
            return self.temperatures.get(sensor_id, None)
