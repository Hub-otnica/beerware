import json
import time
from collections import deque

from PySide6.QtCore import QSize, Qt, QTimer
from PySide6.QtGui import QColor, QFont, QIcon, QPen, QPixmap
from PySide6.QtWidgets import (
    QButtonGroup,
    QDialog,
    QDialogButtonBox,
    QGridLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QPushButton,
    QRadioButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)
from PySide6.QtCharts import QChart, QChartView, QLineSeries, QValueAxis


class SensorSetupDialog(QDialog):
    def __init__(self, config, thermometer_system, save_callback, parent=None):
        super().__init__(parent)
        self.config = config
        self.thermometer_system = thermometer_system
        self.save_callback = save_callback
        self.sensor_labels = dict(config.get("sensor_labels", {}))
        self.primary_sensor_id = config.get("primary_sensor_id")
        self.sensor_rows = {}
        self.seen_sensor_ids = set(thermometer_system.get_sensor_ids())
        self.current_sensor_ids = []

        self.setWindowTitle("Sensor Setup")
        self.setModal(True)
        self.resize(860, 520)
        self.setStyleSheet(
            """
            QDialog {
                background-color: #1F1F24;
                color: #F5F0E6;
            }
            QLabel#statusBadge {
                padding: 3px 8px;
                border-radius: 10px;
                background-color: #3A3A45;
            }
            QLineEdit {
                padding: 6px;
                background-color: #2B2D36;
                border: 1px solid #535665;
                color: #F5F0E6;
            }
            QPushButton {
                padding: 8px 14px;
            }
            """
        )

        layout = QVBoxLayout(self)

        header = QLabel(
            "Plug in DS18B20 probes and assign each detected ID to a role."
        )
        header.setFont(QFont("Roboto", 15))
        layout.addWidget(header)

        self.instructions_label = QLabel(self)
        self.instructions_label.setWordWrap(True)
        self.instructions_label.setStyleSheet("color: #C9D1D9;")
        layout.addWidget(self.instructions_label)

        refresh_button = QPushButton("Refresh Sensor List", self)
        refresh_button.clicked.connect(self.refresh_rows)
        layout.addWidget(refresh_button, alignment=Qt.AlignLeft)

        self.scroll_area = QScrollArea(self)
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setStyleSheet("border: 1px solid #444857;")
        self.rows_container = QWidget(self.scroll_area)
        self.rows_layout = QGridLayout(self.rows_container)
        self.rows_layout.setContentsMargins(16, 16, 16, 16)
        self.rows_layout.setHorizontalSpacing(16)
        self.rows_layout.setVerticalSpacing(12)
        self.scroll_area.setWidget(self.rows_container)
        layout.addWidget(self.scroll_area)

        self.button_group = QButtonGroup(self)
        self.button_group.setExclusive(True)

        button_box = QDialogButtonBox(
            QDialogButtonBox.Save | QDialogButtonBox.Cancel, self
        )
        button_box.accepted.connect(self.save_and_close)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)

        self.refresh_timer = QTimer(self)
        self.refresh_timer.timeout.connect(self.refresh_rows)
        self.refresh_timer.start(700)

        self.refresh_rows()

    def _status_text(self, sensor_id, new_sensor_ids):
        if sensor_id in new_sensor_ids:
            return "Newly connected"
        if self.sensor_labels.get(sensor_id):
            return "Assigned"
        return "Unassigned"

    def _temperature_text(self, sensor_id):
        temperature = self.thermometer_system.get_temperature(sensor_id)
        if temperature is None:
            return "--.- C"
        return f"{temperature:.2f} C"

    def _clear_rows(self):
        while self.rows_layout.count():
            item = self.rows_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()

        for button in list(self.button_group.buttons()):
            self.button_group.removeButton(button)

        self.sensor_rows = {}

    def _rebuild_rows(self, sensor_ids, new_sensor_ids):
        self._clear_rows()

        headers = ["Control", "Status", "Sensor ID", "Temperature", "Role"]
        for column, title in enumerate(headers):
            label = QLabel(title, self.rows_container)
            label.setFont(QFont("Roboto", 12))
            label.setStyleSheet("color: #FBBD0D; font-weight: bold;")
            self.rows_layout.addWidget(label, 0, column)

        if not sensor_ids:
            self.instructions_label.setText(
                "No sensors detected yet. Open this screen, then plug in a DS18B20 probe."
            )
            empty = QLabel(
                "No DS18B20 probes are currently visible to the application.",
                self.rows_container,
            )
            empty.setStyleSheet("color: #C9D1D9;")
            self.rows_layout.addWidget(empty, 1, 0, 1, len(headers))
            return

        self.instructions_label.setText(
            "New probes will appear here automatically. Enter a role name like Wort, Jacket, Kettle 1, or Kettle 3 and choose which sensor controls heating."
        )

        for row, sensor_id in enumerate(sensor_ids, start=1):
            radio = QRadioButton(self.rows_container)
            self.button_group.addButton(radio)
            if sensor_id == self.primary_sensor_id:
                radio.setChecked(True)
            self.rows_layout.addWidget(radio, row, 0, alignment=Qt.AlignCenter)

            status_label = QLabel(
                self._status_text(sensor_id, new_sensor_ids), self.rows_container
            )
            status_label.setObjectName("statusBadge")
            self.rows_layout.addWidget(status_label, row, 1)

            sensor_id_label = QLabel(sensor_id, self.rows_container)
            sensor_id_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
            self.rows_layout.addWidget(sensor_id_label, row, 2)

            temp_label = QLabel(self._temperature_text(sensor_id), self.rows_container)
            self.rows_layout.addWidget(temp_label, row, 3)

            role_edit = QLineEdit(self.rows_container)
            role_edit.setPlaceholderText("Enter role name")
            role_edit.setText(self.sensor_labels.get(sensor_id, ""))
            self.rows_layout.addWidget(role_edit, row, 4)

            self.sensor_rows[sensor_id] = {
                "radio": radio,
                "status_label": status_label,
                "temp_label": temp_label,
                "role_edit": role_edit,
            }

    def refresh_rows(self):
        sensor_ids = self.thermometer_system.get_sensor_ids()
        sensor_ids_changed = sensor_ids != self.current_sensor_ids
        new_sensor_ids = set(sensor_ids) - self.seen_sensor_ids

        if sensor_ids_changed:
            self._rebuild_rows(sensor_ids, new_sensor_ids)
            self.current_sensor_ids = list(sensor_ids)
            self.seen_sensor_ids.update(sensor_ids)
            return

        if not sensor_ids:
            return

        for sensor_id, row in self.sensor_rows.items():
            row["temp_label"].setText(self._temperature_text(sensor_id))
            row["status_label"].setText(self._status_text(sensor_id, set()))

    def save_and_close(self):
        updated_labels = dict(self.config.get("sensor_labels", {}))

        for sensor_id, row in self.sensor_rows.items():
            role = row["role_edit"].text().strip()
            if role:
                updated_labels[sensor_id] = role
            else:
                updated_labels.pop(sensor_id, None)

        primary_sensor_id = None
        for sensor_id, row in self.sensor_rows.items():
            if row["radio"].isChecked():
                primary_sensor_id = sensor_id
                break

        self.save_callback(updated_labels, primary_sensor_id)
        self.accept()

    def closeEvent(self, event):
        self.refresh_timer.stop()
        super().closeEvent(event)


class MainWindow(QMainWindow):
    def __init__(self, config, config_path="config.json"):
        super().__init__()

        self.config = config
        self.config_path = config_path
        self.temp_target = config.get("default_temp", 25.0)
        self.simulation_mode = config.get("simulation_mode", False)
        self.sensor_labels = config.get("sensor_labels", {})
        self.sensor_offsets = config.get("sensor_offsets", {})
        self.control_mode = config.get("control_mode", "on_off")
        self.pid_settings = config.get("pid", {})
        self.pid_kp = self.pid_settings.get("kp", 0.15)
        self.pid_ki = self.pid_settings.get("ki", 0.005)
        self.pid_kd = self.pid_settings.get("kd", 0.04)
        self.pid_window_seconds = max(
            0.5,
            self.pid_settings.get("window_seconds", 2.0),
        )
        self.pid_integral_min = self.pid_settings.get("integral_min", -10.0)
        self.pid_integral_max = self.pid_settings.get("integral_max", 10.0)
        self.pid_integral = 0.0
        self.pid_last_error = None
        self.pid_last_time = None
        self.pid_last_output = 0.0
        self.graph_window_seconds = config.get("graph_window_seconds", 240.0)
        self.graph_history = deque()
        self.graph_start_time = time.monotonic()
        self._systems_stopped = False
        self.secondary_temp_labels = {}
        self.sensor_ids = []
        self.secondary_sensor_ids = []
        self.primary_sensor_id = config.get("primary_sensor_id")

        self.heating_system, self.thermometer_system = self._build_systems()
        self.heating_system.start()
        self.thermometer_system.start()
        self._sync_sensor_state()

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
            self.config.get("sensor_update_interval", 0.3),
            offsets=self.sensor_offsets,
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
        self.mode_label.setFont(QFont("Roboto", 16))
        self.mode_label.setGeometry(20, 20, 330, 32)

        self.control_button = QPushButton(self)
        self.control_button.setFont(QFont("Roboto", 12))
        self.control_button.setGeometry(360, 20, 180, 32)
        self.control_button.clicked.connect(self.toggle_control_mode)

        self.sensor_setup_button = QPushButton("Sensor Setup", self)
        self.sensor_setup_button.setFont(QFont("Roboto", 12))
        self.sensor_setup_button.setStyleSheet(
            "background-color: #145DA0; color: white;"
        )
        self.sensor_setup_button.setGeometry(550, 20, 160, 32)
        self.sensor_setup_button.clicked.connect(self.open_sensor_setup)

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

        self._build_graph()

        self.temp_target_label = QLabel(self)
        self.temp_target_label.setFont(QFont("Roboto", 26))

        self.b_plus = QPushButton("+", self)
        self.b_plus.setFont(QFont("Roboto", 36))
        self.b_plus.setStyleSheet("background-color: #4E9F3D; color: white;")
        self.b_plus.setGeometry(0, self.height() - 100, 200, 100)
        self.b_plus.clicked.connect(self.b_plus_clicked)

        self.b_minus = QPushButton("-", self)
        self.b_minus.setFont(QFont("Roboto", 36))
        self.b_minus.setStyleSheet("background-color: #2C74B3; color: white;")
        self.b_minus.setGeometry(self.width() - 200, self.height() - 100, 200, 100)
        self.b_minus.clicked.connect(self.b_minus_clicked)

        self.exit_button = QPushButton("X", self)
        self.exit_button.setFont(QFont("Roboto", 14))
        self.exit_button.setStyleSheet("background-color: #C1121F; color: white;")
        self.exit_button.setGeometry(self.width() - 58, 14, 44, 36)
        self.exit_button.clicked.connect(self.exit_app)

        self._update_control_button()
        self._rebuild_sensor_labels()
        self.b_plus.raise_()
        self.b_minus.raise_()
        self.exit_button.raise_()

        self.showFullScreen()

    def _sync_sensor_state(self):
        sensor_ids = self.thermometer_system.get_sensor_ids()
        sensor_ids_changed = sensor_ids != self.sensor_ids
        self.sensor_ids = sensor_ids

        if self.primary_sensor_id not in self.sensor_ids:
            configured_primary = self.config.get("primary_sensor_id")
            if configured_primary in self.sensor_ids:
                self.primary_sensor_id = configured_primary
            else:
                self.primary_sensor_id = self.sensor_ids[0] if self.sensor_ids else None

        self.secondary_sensor_ids = [
            sensor_id for sensor_id in self.sensor_ids if sensor_id != self.primary_sensor_id
        ]

        if sensor_ids_changed and hasattr(self, "temp_label"):
            self._rebuild_sensor_labels()

    def _rebuild_sensor_labels(self):
        for label in self.secondary_temp_labels.values():
            label.deleteLater()
        self.secondary_temp_labels = {}

        for index, sensor_id in enumerate(self.secondary_sensor_ids):
            label = QLabel(self)
            label.setFont(QFont("Roboto", 22))
            label.move(20, 160 + (index * 45))
            self.secondary_temp_labels[sensor_id] = label

        target_y = 160 + (len(self.secondary_sensor_ids) * 45) + 20
        self.temp_target_label.move(20, target_y)

    def open_sensor_setup(self):
        dialog = SensorSetupDialog(
            self.config,
            self.thermometer_system,
            self.apply_sensor_setup,
            self,
        )
        dialog.exec()

    def apply_sensor_setup(self, sensor_labels, primary_sensor_id):
        self.sensor_labels = sensor_labels
        self.config["sensor_labels"] = sensor_labels
        self.primary_sensor_id = primary_sensor_id
        self.config["primary_sensor_id"] = primary_sensor_id
        self._save_config()
        self._sync_sensor_state()
        self.refresh_display()

    def _save_config(self):
        with open(self.config_path, "w", encoding="utf-8") as config_file:
            json.dump(self.config, config_file, indent=4)
            config_file.write("\n")

    def sensor_label(self, sensor_id):
        return self.sensor_labels.get(sensor_id, sensor_id)

    def format_temperature(self, sensor_id):
        temperature = self.thermometer_system.get_temperature(sensor_id)
        label = self.sensor_label(sensor_id)
        if temperature is None:
            return f"{label}: --.- C"
        return f"{label}: {temperature:.2f} C"

    def refresh_display(self):
        self._sync_sensor_state()

        mode_name = "Simulation" if self.simulation_mode else "Hardware"
        control_name = "PID" if self.control_mode == "pid" else "ON/OFF"
        self.mode_label.setText(f"Mode: {mode_name} | Ctrl: {control_name}")
        self._update_control_button()

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
        self._update_temperature_graph(current_temp)
        if current_temp is None:
            self.heating_off()
            return

        self._run_heating_control(current_temp)

    def _run_heating_control(self, current_temp):
        if self.control_mode == "pid":
            self._run_pid_control(current_temp)
            return

        self._run_on_off_control(current_temp)

    def _run_on_off_control(self, current_temp):
        if current_temp < self.temp_target:
            self.heating_on()
        else:
            self.heating_off()

    def _run_pid_control(self, current_temp):
        now = time.monotonic()
        error = self.temp_target - current_temp

        if self.pid_last_time is None:
            dt = 0.0
        else:
            dt = max(now - self.pid_last_time, 1e-6)

        if dt > 0:
            self.pid_integral += error * dt
            self.pid_integral = max(
                self.pid_integral_min,
                min(self.pid_integral_max, self.pid_integral),
            )

        derivative = 0.0
        if dt > 0 and self.pid_last_error is not None:
            derivative = (error - self.pid_last_error) / dt

        pid_output = (
            (self.pid_kp * error)
            + (self.pid_ki * self.pid_integral)
            + (self.pid_kd * derivative)
        )
        self.pid_last_output = max(0.0, min(1.0, pid_output))
        self.pid_last_error = error
        self.pid_last_time = now

        heater_should_be_on = False
        if self.pid_last_output >= 1.0:
            heater_should_be_on = True
        elif self.pid_last_output > 0:
            window_position = now % self.pid_window_seconds
            heater_should_be_on = window_position < (
                self.pid_last_output * self.pid_window_seconds
            )

        self._set_heater(heater_should_be_on)

    def _update_control_button(self):
        if self.control_mode == "pid":
            self.control_button.setText("Switch To ON/OFF")
            self.control_button.setStyleSheet("background-color: #8E7DBE; color: white;")
        else:
            self.control_button.setText("Switch To PID")
            self.control_button.setStyleSheet("background-color: #B87333; color: white;")

    def toggle_control_mode(self):
        if self.control_mode == "pid":
            self.control_mode = "on_off"
        else:
            self.control_mode = "pid"
        self._reset_pid_state()
        self._update_control_button()

    def _reset_pid_state(self):
        self.pid_integral = 0.0
        self.pid_last_error = None
        self.pid_last_time = None
        self.pid_last_output = 0.0

    def _update_target_label(self):
        control_sensor_name = self.sensor_label(self.primary_sensor_id) if self.primary_sensor_id else "sensor"
        self.temp_target_label.setText(
            f"Target ({control_sensor_name}): {self.temp_target:.2f} C"
        )
        self.temp_target_label.adjustSize()

    def _update_heater_status(self):
        heater_status = "ON" if self.heating_system.heater0 else "OFF"
        if self.control_mode == "pid":
            duty = self.pid_last_output * 100
            self.heater_state_label.setText(f"Heater 1: {heater_status} ({duty:.0f}% duty)")
        else:
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
        self._set_heater(True)

    def heating_off(self):
        self._set_heater(False)

    def _set_heater(self, enabled):
        if enabled:
            self.heating_label.setPixmap(QPixmap("./pics/heating_on.png"))
        else:
            self.heating_label.setPixmap(QPixmap("./pics/heating_off.png"))
        self.heating_label.adjustSize()
        self.heating_system.heater0 = enabled
        self._update_heater_status()

    def _build_graph(self):
        self.temperature_series = QLineSeries()

        self.time_axis = QValueAxis()
        self.time_axis.setTitleText("Time (s)")
        self.time_axis.setRange(0, self.graph_window_seconds)
        self.time_axis.setLabelFormat("%d")

        self.temp_axis = QValueAxis()
        self.temp_axis.setTitleText("Temp (C)")
        self.temp_axis.setRange(0, 100)
        self.temp_axis.setLabelFormat("%.1f")

        self.chart = QChart()
        self.chart.addSeries(self.temperature_series)
        self.chart.addAxis(self.time_axis, Qt.AlignBottom)
        self.chart.addAxis(self.temp_axis, Qt.AlignLeft)
        self.temperature_series.attachAxis(self.time_axis)
        self.temperature_series.attachAxis(self.temp_axis)
        self.chart.legend().hide()
        self.chart.setBackgroundBrush(QColor("#1E1E1E"))
        self.chart.setPlotAreaBackgroundVisible(True)
        self.chart.setPlotAreaBackgroundBrush(QColor("#2A2A2A"))

        self.chart_view = QChartView(self.chart, self)
        self.chart_view.setGeometry(360, 250, self.width() - 380, self.height() - 370)

        self._update_graph_style()

    def _update_graph_style(self):
        if self.control_mode == "pid":
            color = QColor("#4CC9F0")
        else:
            color = QColor("#FB8500")

        pen = QPen(color)
        pen.setWidth(3)
        self.temperature_series.setPen(pen)

    def _update_temperature_graph(self, current_temp):
        self._update_graph_style()
        if current_temp is None:
            return

        elapsed = time.monotonic() - self.graph_start_time
        self.graph_history.append((elapsed, current_temp))

        window_start = max(0.0, elapsed - self.graph_window_seconds)
        while self.graph_history and self.graph_history[0][0] < window_start:
            self.graph_history.popleft()

        self.temperature_series.clear()
        for point_time, point_temp in self.graph_history:
            self.temperature_series.append(point_time - window_start, point_temp)

        self.time_axis.setRange(0, self.graph_window_seconds)
        self._update_temp_axis_from_history()

    def _update_temp_axis_from_history(self):
        if not self.graph_history:
            self.temp_axis.setRange(0, 100)
            return

        min_temp = min(point[1] for point in self.graph_history)
        max_temp = max(point[1] for point in self.graph_history)

        padding = max(0.5, (max_temp - min_temp) * 0.2)
        self.temp_axis.setRange(min_temp - padding, max_temp + padding)
