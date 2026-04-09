from gpiozero import OutputDevice
import threading
import time

class Heating:
    def __init__(self, heater0_pin, heater1_pin, update_interval=20.0, buffer_interval=0.3):
        self._heater0 = False
        self._heater1 = False
        self.heater0_relay = OutputDevice(heater0_pin, active_high=True, initial_value=False)
        self.heater1_relay = OutputDevice(heater1_pin, active_high=True, initial_value=False)
        self.swap_interval = update_interval
        self.swap_buffer_interval = buffer_interval
        self._running = False
        self._thread = None
        self._lock = threading.Lock()
        self._state_changed = threading.Event()

    @property
    def heater0(self):
        with self._lock:
            return self._heater0

    @heater0.setter
    def heater0(self, enabled):
        with self._lock:
            self._heater0 = enabled
        self._state_changed.set()

    @property
    def heater1(self):
        with self._lock:
            return self._heater1

    @heater1.setter
    def heater1(self, enabled):
        with self._lock:
            self._heater1 = enabled
        self._state_changed.set()

    def _get_requested_states(self):
        with self._lock:
            return self._heater0, self._heater1

    def _apply_outputs(self, heater0_output, heater1_output):
        if not heater0_output:
            self.heater0_relay.off()

        if not heater1_output:
            self.heater1_relay.off()

        if heater0_output:
            self.heater0_relay.on()

        if heater1_output:
            self.heater1_relay.on()

    def _run(self):
        toggle = False
        try:
            while self._running:
                heater0, heater1 = self._get_requested_states()

                if heater0 and heater1:
                    # Safety off before toggling
                    self._apply_outputs(False, False)
                    if self._state_changed.wait(self.swap_buffer_interval):
                        self._state_changed.clear()
                        continue

                    heater0, heater1 = self._get_requested_states()
                    if not (heater0 and heater1):
                        continue

                    toggle = not toggle
                    if toggle:
                        self._apply_outputs(True, False)
                    else:
                        self._apply_outputs(False, True)

                    if self._state_changed.wait(self.swap_interval):
                        self._state_changed.clear()
                else:
                    self._apply_outputs(heater0, heater1)
                    self._state_changed.wait()
                    self._state_changed.clear()
        finally:
            self._apply_outputs(False, False)

    def start(self):
        if not self._running:
            self._running = True
            self._thread = threading.Thread(target=self._run, daemon=True)
            self._thread.start()

    def stop(self):
        self._running = False
        self._state_changed.set()
        if self._thread is not None:
            self._thread.join()
            self._thread = None
        self._apply_outputs(False, False)
