import time

from src.simulation import SimulatedHeating, SimulatedThermometers


class FixedOutputHeating:
    def __init__(self, heater0_output=False, heater1_output=False):
        self._heater0_output = heater0_output
        self._heater1_output = heater1_output

    def get_output_states(self):
        return self._heater0_output, self._heater1_output


def test_simulated_heating_single_heater_output():
    heating = SimulatedHeating(update_interval=0.02, buffer_interval=0.005)
    heating.start()
    try:
        heating.heater0 = True
        heating.heater1 = False
        time.sleep(0.05)
        assert heating.get_output_states() == (True, False)
    finally:
        heating.stop()


def test_simulated_heating_alternates_when_both_requested():
    heating = SimulatedHeating(update_interval=0.02, buffer_interval=0.005)
    heating.heater0 = True
    heating.heater1 = True
    heating.start()

    observed_states = set()
    try:
        end_time = time.time() + 0.25
        while time.time() < end_time:
            observed_states.add(heating.get_output_states())
            time.sleep(0.01)

        assert (True, False) in observed_states
        assert (False, True) in observed_states
        assert (True, True) not in observed_states
    finally:
        heating.stop()


def test_simulated_thermometers_step_populates_temperatures():
    heating = FixedOutputHeating(False, False)
    thermometers = SimulatedThermometers(
        heating,
        {
            "noise_amplitude": 0.0,
            "initial_wort_temp": 21.5,
            "initial_jacket_temp": 21.0,
        },
    )

    thermometers._step_physics()

    assert thermometers.get_temperature("sim_wort") is not None
    assert thermometers.get_temperature("sim_jacket") is not None
    assert thermometers.get_temperature("missing_sensor") is None


def test_simulated_thermometers_jacket_warms_when_heater_is_on():
    heating = FixedOutputHeating(True, False)
    initial_jacket_temp = 21.0
    thermometers = SimulatedThermometers(
        heating,
        {
            "noise_amplitude": 0.0,
            "update_interval": 0.1,
            "heater_gain": 3.0,
            "jacket_cooling": 0.01,
            "wort_cooling": 0.0,
            "transfer_rate": 0.02,
            "ambient_temp": 20.0,
            "initial_wort_temp": 21.0,
            "initial_jacket_temp": initial_jacket_temp,
            "jacket_sensor_lag": 0.4,
        },
    )

    for _ in range(40):
        thermometers._step_physics()

    assert thermometers.get_temperature("sim_jacket") > initial_jacket_temp


def test_simulated_thermometers_thread_updates_readings():
    heating = FixedOutputHeating(False, False)
    thermometers = SimulatedThermometers(
        heating,
        {
            "noise_amplitude": 0.0,
            "update_interval": 0.01,
        },
    )

    thermometers.start()
    try:
        time.sleep(0.05)
        assert thermometers.get_temperature("sim_wort") is not None
        assert thermometers.get_temperature("sim_jacket") is not None
    finally:
        thermometers.stop()
