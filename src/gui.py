from PySide6.QtCore import QSize, QTimer
from PySide6.QtGui import QFont, QIcon, QPixmap
from PySide6.QtWidgets import QApplication, QLabel, QMainWindow, QPushButton


class MainWindow(QMainWindow):
    def __init__(self, config):
        super().__init__()

        self.config = config
        self.temp_target = config.get("default_temp", 25.0)
        self.simulation_mode = config.get("simulation_mode", False)
        self.sensor_labels = config.get("sensor_labels", {})
        self._systems_stopped = False

        self.heating_system, self.thermometer_system = self._build_systems()
        self.heating_system.start()
        self.thermometer_system.start()

        self.sensor_ids = list(self.thermometer_system.temperatures.keys())
        self.primary_sensor_id = config.get("primary_sensor_id")
        if self.primary_sensor_id not in self.sensor_ids:
            self.primary_sensor_id = self.sensor_ids[0] if self.sensor_ids else None
        self.secondary_sensor_ids = [
            sensor_id for sensor_id in self.sensor_ids if sensor_id != self.primary_sensor_id
        ]

        self._build_ui()

        self.refresh_timer = QTimer(self)
        self.refresh_timer.timeout.connect(self.refresh_display)
        self.refresh_timer.start(250)
        self.refresh_display()

    def _build_systems(self):
        heater_pins = self.config.get("heater_pins", [18, 10])
        heater_swap_interval = self.config.get("heater_swap_interval", 3.0)
        heater_buffer_interval = self.config.get("heater_buffer_interval", 0.3)

        if self.simulation_mode:
            from src.simulation import SimulatedHeating, SimulatedThermometers

            heating_system = SimulatedHeating(
                update_interval=heater_swap_interval,
                buffer_interval=heater_buffer_interval,
            )
            thermometer_system = SimulatedThermometers(
                heating_system,
                self.config.get("simulation", {}),
            )
            return heating_system, thermometer_system

        from src.heating import Heating
        from src.thermometers import Thermometers

        heating_system = Heating(
            heater_pins[0],
            heater_pins[1],
            heater_swap_interval,
            heater_buffer_interval,
        )
        thermometer_system = Thermometers(
            self.config.get("sensor_update_interval", 0.3)
        )
        return heating_system, thermometer_system

    def _build_ui(self):
        window_height = self.config.get("screen_height", 600)
        window_width = self.config.get("screen_width", 1024)

        self.setWindowTitle("BeerWare")
        self.setFixedSize(QSize(window_width, window_height))
        self.setWindowIcon(QIcon("./pics/beer_pic.png"))
        self.setStyleSheet(
            """
            background-color: #2D2C2E;
            color: #FBBD0D;
            """
        )

        self.mode_label = QLabel(self)
        self.mode_label.setFont(QFont("Roboto", 18))
        self.mode_label.move(20, 20)

        self.heating_label = QLabel(self)
        self.heating_label.setPixmap(QPixmap("./pics/heating_off.png"))
        self.heating_label.adjustSize()
        self.heating_label.move(self.width() - self.heating_label.width() - 20, 20)

        self.heater_state_label = QLabel(self)
        self.heater_state_label.setFont(QFont("Roboto", 20))
        self.heater_state_label.move(self.width() - 260, 180)

        self.temp_label = QLabel(self)
        self.temp_label.setFont(QFont("Roboto", 32))
        self.temp_label.move(20, 80)

        self.secondary_temp_labels = {}
        for index, sensor_id in enumerate(self.secondary_sensor_ids):
            label = QLabel(self)
            label.setFont(QFont("Roboto", 24))
            label.move(20, 160 + (index * 45))
            self.secondary_temp_labels[sensor_id] = label

        target_y = 160 + (len(self.secondary_sensor_ids) * 45) + 30
        self.temp_target_label = QLabel(self)
        self.temp_target_label.setFont(QFont("Roboto", 30))
        self.temp_target_label.move(20, target_y)

        self.hint_label = QLabel("Use +/- to change target temperature", self)
        self.hint_label.setFont(QFont("Roboto", 18))
        self.hint_label.move(20, target_y + 55)

        b_plus = QPushButton("+", self)
        b_plus.setGeometry(0, self.height() - 100, 200, 100)
        b_plus.clicked.connect(self.b_plus_clicked)

        b_minus = QPushButton("-", self)
        b_minus.setGeometry(self.width() - 200, self.height() - 100, 200, 100)
        b_minus.clicked.connect(self.b_minus_clicked)

        exit_button = QPushButton("EXIT", self)
        exit_button.setStyleSheet("background-color: red; color: white; font-size: 32px;")
        exit_button.setGeometry(
            (self.width() // 2) - 150,
            self.height() - 220,
            300,
            100,
        )
        exit_button.clicked.connect(self.exit_app)

        self.showFullScreen()

    def sensor_label(self, sensor_id):
        return self.sensor_labels.get(sensor_id, sensor_id)

    def format_temperature(self, sensor_id):
        temperature = self.thermometer_system.get_temperature(sensor_id)
        label = self.sensor_label(sensor_id)
        if temperature is None:
            return f"{label}: --.- C"
        return f"{label}: {temperature:.2f} C"

    def refresh_display(self):
        mode_name = "Simulation" if self.simulation_mode else "Hardware"
        self.mode_label.setText(f"Mode: {mode_name}")
        self.mode_label.adjustSize()

        if self.primary_sensor_id is None:
            self.temp_label.setText("No sensors detected")
            self.temp_label.adjustSize()
            self.heating_off()
            self._update_target_label()
            return

        self.temp_label.setText(self.format_temperature(self.primary_sensor_id))
        self.temp_label.adjustSize()

        for sensor_id, label in self.secondary_temp_labels.items():
            label.setText(self.format_temperature(sensor_id))
            label.adjustSize()

        self._update_target_label()

        current_temp = self.thermometer_system.get_temperature(self.primary_sensor_id)
        if current_temp is None:
            self.heating_off()
            return

        if current_temp < self.temp_target:
            self.heating_on()
        else:
            self.heating_off()

    def _update_target_label(self):
        control_sensor_name = self.sensor_label(self.primary_sensor_id) if self.primary_sensor_id else "sensor"
        self.temp_target_label.setText(
            f"Target ({control_sensor_name}): {self.temp_target:.2f} C"
        )
        self.temp_target_label.adjustSize()

    def _update_heater_status(self):
        heater_status = "ON" if self.heating_system.heater0 else "OFF"
        self.heater_state_label.setText(f"Heater 1: {heater_status}")
        self.heater_state_label.adjustSize()

    def exit_app(self):
        self.close()

    def closeEvent(self, event):
        self._shutdown_systems()
        super().closeEvent(event)

    def _shutdown_systems(self):
        if self._systems_stopped:
            return

        self._systems_stopped = True
        self.refresh_timer.stop()
        self.heating_system.stop()
        self.thermometer_system.stop()

    def b_plus_clicked(self):
        self.temp_target += 1
        self._update_target_label()

    def b_minus_clicked(self):
        self.temp_target -= 1
        self._update_target_label()

    def heating_on(self):
        self.heating_label.setPixmap(QPixmap("./pics/heating_on.png"))
        self.heating_label.adjustSize()
        self.heating_system.heater0 = True
        self._update_heater_status()

    def heating_off(self):
        self.heating_label.setPixmap(QPixmap("./pics/heating_off.png"))
        self.heating_label.adjustSize()
        self.heating_system.heater0 = False
        self._update_heater_status()
