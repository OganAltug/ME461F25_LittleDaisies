# qrd_gui.py (PC side)
import sys, time, csv
from collections import deque

import numpy as np
import serial
import serial.tools.list_ports

from PySide6 import QtCore, QtWidgets
import pyqtgraph as pg


BAUD = 115200

# Stream packet format expected from Pico:
#   I,.... (info lines)
#   S,<t_ms>,<raw_u16>,<voltage_V>

class QRDCalibrator:
    """
    Holds calibration points (V, mm) and provides linear interpolation V->mm.
    Also provides local slope dd/dV for resolution estimation.
    """
    def __init__(self):
        self.points = []  # list of (V, mm)
        self._v_sorted = None
        self._d_sorted = None
        self.ready = False

    def clear(self):
        self.points = []
        self._v_sorted = None
        self._d_sorted = None
        self.ready = False

    def add_point(self, v, d_mm):
        self.points.append((float(v), float(d_mm)))
        self.ready = False

    def build(self):
        if len(self.points) < 3:
            self.ready = False
            return False, "Need at least 3 points."
        pts = np.array(self.points, dtype=float)

        v = pts[:, 0]
        d = pts[:, 1]

        # sort by voltage (required for np.interp)
        idx = np.argsort(v)
        v = v[idx]
        d = d[idx]

        # check monotonic-ish (at least increasing voltage axis)
        # duplicates can break slope; we remove near-duplicates
        vv = [v[0]]
        dd = [d[0]]
        for i in range(1, len(v)):
            if abs(v[i] - vv[-1]) > 1e-5:
                vv.append(v[i])
                dd.append(d[i])
        v = np.array(vv, dtype=float)
        d = np.array(dd, dtype=float)

        if len(v) < 3:
            self.ready = False
            return False, "Too many duplicate voltages; collect cleaner points."

        self._v_sorted = v
        self._d_sorted = d
        self.ready = True
        return True, f"Interpolator built with {len(v)} unique points."

    def estimate_mm(self, v):
        if not self.ready:
            return None
        v = float(v)
        # clamp to bounds (to avoid insane extrapolation)
        vmin, vmax = self._v_sorted[0], self._v_sorted[-1]
        v_clamped = min(max(v, vmin), vmax)
        return float(np.interp(v_clamped, self._v_sorted, self._d_sorted))

    def slope_dd_dv(self, v):
        """
        local slope dd/dV around v using nearest segment in piecewise linear curve.
        """
        if not self.ready:
            return None
        v = float(v)
        vs = self._v_sorted
        ds = self._d_sorted

        # clamp to inside
        if v <= vs[0]:
            i = 0
        elif v >= vs[-1]:
            i = len(vs) - 2
        else:
            i = int(np.searchsorted(vs, v) - 1)
            i = max(0, min(i, len(vs) - 2))

        dv = vs[i+1] - vs[i]
        if abs(dv) < 1e-9:
            return None
        return float((ds[i+1] - ds[i]) / dv)


class MainWindow(QtWidgets.QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("QRD1114 Step5 - Distance Calibration & Metrics (PySide6)")

        # Serial
        self.ser = None
        self.connected = False

        # Buffers
        self.stream = deque(maxlen=6000)   # store (t_s, raw, v)
        self.capture_on = False

        # Calibration + accuracy test
        self.cal = QRDCalibrator()
        self.acc_tests = []  # list of (true_mm, est_mm, v)

        # UI
        self._build_ui()

        # timer for polling serial
        self.timer = QtCore.QTimer(self)
        self.timer.timeout.connect(self.poll_serial)
        self.timer.start(30)

    # ---------------- UI ----------------
    def _build_ui(self):
        cw = QtWidgets.QWidget()
        self.setCentralWidget(cw)
        layout = QtWidgets.QVBoxLayout(cw)

        # Top controls
        top = QtWidgets.QHBoxLayout()
        layout.addLayout(top)

        # Connection group
        g_conn = QtWidgets.QGroupBox("Connection")
        top.addWidget(g_conn)
        gl = QtWidgets.QGridLayout(g_conn)

        self.cb_ports = QtWidgets.QComboBox()
        self.btn_refresh = QtWidgets.QPushButton("Refresh")
        self.btn_connect = QtWidgets.QPushButton("Connect")
        self.lbl_status = QtWidgets.QLabel("Disconnected")

        gl.addWidget(self.cb_ports, 0, 0, 1, 2)
        gl.addWidget(self.btn_refresh, 1, 0)
        gl.addWidget(self.btn_connect, 1, 1)
        gl.addWidget(self.lbl_status, 2, 0, 1, 2)

        self.btn_refresh.clicked.connect(self.refresh_ports)
        self.btn_connect.clicked.connect(self.toggle_connect)
        self.refresh_ports()

        # Stream/Capture group
        g_cap = QtWidgets.QGroupBox("Live Stream")
        top.addWidget(g_cap)
        gl2 = QtWidgets.QGridLayout(g_cap)

        self.btn_capture = QtWidgets.QPushButton("Start Capture")
        self.btn_capture.setEnabled(False)

        self.spin_window = QtWidgets.QSpinBox()
        self.spin_window.setRange(1, 120)
        self.spin_window.setValue(10)

        self.lbl_live = QtWidgets.QLabel("V=-   raw=-   est_mm=-")

        gl2.addWidget(QtWidgets.QLabel("Plot Window (s):"), 0, 0)
        gl2.addWidget(self.spin_window, 0, 1)
        gl2.addWidget(self.btn_capture, 1, 0, 1, 2)
        gl2.addWidget(self.lbl_live, 2, 0, 1, 2)

        self.btn_capture.clicked.connect(self.toggle_capture)

        # Calibration group
        g_cal = QtWidgets.QGroupBox("Calibration (V → mm via interpolation)")
        top.addWidget(g_cal, stretch=1)
        gl3 = QtWidgets.QGridLayout(g_cal)

        self.edit_true_mm = QtWidgets.QLineEdit("10.0")
        self.btn_add_cal = QtWidgets.QPushButton("Add Cal Point (avg V)")
        self.btn_build = QtWidgets.QPushButton("Build Interpolator")
        self.btn_clear_cal = QtWidgets.QPushButton("Clear Cal")
        self.lbl_cal_state = QtWidgets.QLabel("No interpolator")

        self.table_cal = QtWidgets.QTableWidget(0, 2)
        self.table_cal.setHorizontalHeaderLabels(["Voltage (V)", "Distance (mm)"])
        self.table_cal.horizontalHeader().setStretchLastSection(True)
        self.table_cal.setMaximumHeight(160)

        gl3.addWidget(QtWidgets.QLabel("True distance (mm):"), 0, 0)
        gl3.addWidget(self.edit_true_mm, 0, 1)
        gl3.addWidget(self.btn_add_cal, 0, 2)

        gl3.addWidget(self.btn_build, 1, 2)
        gl3.addWidget(self.btn_clear_cal, 1, 1)
        gl3.addWidget(self.lbl_cal_state, 1, 0)

        gl3.addWidget(self.table_cal, 2, 0, 1, 3)

        self.btn_add_cal.clicked.connect(self.add_cal_point)
        self.btn_build.clicked.connect(self.build_calibrator)
        self.btn_clear_cal.clicked.connect(self.clear_cal)

        # Metrics group
        g_met = QtWidgets.QGroupBox("Metrics")
        top.addWidget(g_met)
        gl4 = QtWidgets.QGridLayout(g_met)

        self.spin_rep_sec = QtWidgets.QSpinBox()
        self.spin_rep_sec.setRange(1, 20)
        self.spin_rep_sec.setValue(2)

        self.btn_repeat = QtWidgets.QPushButton("Repeatability Now")
        self.btn_repeat.setEnabled(False)

        self.text_metrics = QtWidgets.QPlainTextEdit()
        self.text_metrics.setReadOnly(True)
        self.text_metrics.setMaximumWidth(380)

        gl4.addWidget(QtWidgets.QLabel("Repeatability window (s):"), 0, 0)
        gl4.addWidget(self.spin_rep_sec, 0, 1)
        gl4.addWidget(self.btn_repeat, 1, 0, 1, 2)
        gl4.addWidget(self.text_metrics, 2, 0, 1, 2)

        self.btn_repeat.clicked.connect(self.compute_repeatability)

        # Accuracy test group
        g_acc = QtWidgets.QGroupBox("Accuracy Test (optional)")
        layout.addWidget(g_acc)
        acc_l = QtWidgets.QGridLayout(g_acc)

        self.edit_acc_true = QtWidgets.QLineEdit("15.0")
        self.btn_acc_add = QtWidgets.QPushButton("Add Test Point")
        self.btn_acc_clear = QtWidgets.QPushButton("Clear Tests")
        self.lbl_acc = QtWidgets.QLabel("No tests yet")

        acc_l.addWidget(QtWidgets.QLabel("True distance (mm):"), 0, 0)
        acc_l.addWidget(self.edit_acc_true, 0, 1)
        acc_l.addWidget(self.btn_acc_add, 0, 2)
        acc_l.addWidget(self.btn_acc_clear, 0, 3)
        acc_l.addWidget(self.lbl_acc, 1, 0, 1, 4)

        self.btn_acc_add.clicked.connect(self.add_accuracy_point)
        self.btn_acc_clear.clicked.connect(self.clear_accuracy)

        # Plots (two)
        plots = QtWidgets.QHBoxLayout()
        layout.addLayout(plots)

        pg.setConfigOptions(antialias=True)

        # Live voltage plot
        self.plot_live = pg.PlotWidget(title="Live Voltage (last N seconds)")
        self.plot_live.setLabel('bottom', 'time (s)')
        self.plot_live.setLabel('left', 'voltage (V)')
        self.curve_live = self.plot_live.plot([], [])
        plots.addWidget(self.plot_live, stretch=2)

        # Calibration curve plot
        self.plot_cal = pg.PlotWidget(title="Calibration: Distance vs Voltage")
        self.plot_cal.setLabel('bottom', 'voltage (V)')
        self.plot_cal.setLabel('left', 'distance (mm)')
        self.scatter_cal = pg.ScatterPlotItem(size=8)
        self.curve_cal = self.plot_cal.plot([], [])
        self.plot_cal.addItem(self.scatter_cal)
        plots.addWidget(self.plot_cal, stretch=2)

        # Export buttons
        exp = QtWidgets.QHBoxLayout()
        layout.addLayout(exp)

        self.btn_save_stream = QtWidgets.QPushButton("Export Stream CSV")
        self.btn_save_cal = QtWidgets.QPushButton("Export Cal CSV")
        self.btn_save_acc = QtWidgets.QPushButton("Export Accuracy CSV")

        exp.addWidget(self.btn_save_stream)
        exp.addWidget(self.btn_save_cal)
        exp.addWidget(self.btn_save_acc)

        self.btn_save_stream.clicked.connect(self.export_stream_csv)
        self.btn_save_cal.clicked.connect(self.export_cal_csv)
        self.btn_save_acc.clicked.connect(self.export_acc_csv)

        self.log("Ready.")

    # ---------------- Helpers ----------------
    def log(self, s):
        ts = time.strftime("%H:%M:%S")
        self.text_metrics.appendPlainText(f"[{ts}] {s}")

    def refresh_ports(self):
        self.cb_ports.clear()
        ports = [p.device for p in serial.tools.list_ports.comports()]
        self.cb_ports.addItems(ports)

    def toggle_connect(self):
        if not self.connected:
            port = self.cb_ports.currentText().strip()
            if not port:
                QtWidgets.QMessageBox.warning(self, "Port", "Select a COM port.")
                return
            try:
                self.ser = serial.Serial(port, BAUD, timeout=0.05)
                self.connected = True
                self.btn_connect.setText("Disconnect")
                self.btn_capture.setEnabled(True)
                self.lbl_status.setText(f"Connected: {port} @ {BAUD}")
                self.log(f"Connected to {port}")
                time.sleep(0.2)
            except Exception as e:
                QtWidgets.QMessageBox.critical(self, "Connect error", str(e))
                self.ser = None
                self.connected = False
        else:
            self.capture_on = False
            if self.ser:
                try:
                    self.ser.close()
                except:
                    pass
            self.ser = None
            self.connected = False
            self.btn_connect.setText("Connect")
            self.btn_capture.setEnabled(False)
            self.btn_repeat.setEnabled(False)
            self.lbl_status.setText("Disconnected")
            self.log("Disconnected.")

    def toggle_capture(self):
        if not self.connected:
            return
        self.capture_on = not self.capture_on
        self.btn_capture.setText("Stop Capture" if self.capture_on else "Start Capture")
        if self.capture_on:
            self.log("Capture ON (storing + plotting).")
            self.btn_repeat.setEnabled(True)
        else:
            self.log("Capture OFF (still connected, not storing).")

    def poll_serial(self):
        if not (self.ser and self.connected):
            return
        try:
            data = self.ser.read(8192)
            if not data:
                return
            lines = data.decode(errors="ignore").splitlines()
            for ln in lines:
                self.handle_line(ln.strip())
        except Exception as e:
            self.lbl_status.setText("Read error (port busy?)")
            self.log(f"Read error: {e}")

    def handle_line(self, line):
        if not line:
            return
        if line.startswith("I,"):
            # info
            self.log(line)
            return
        if not line.startswith("S,"):
            return

        # S,<t_ms>,<raw_u16>,<voltage_V>
        parts = line.split(",")
        if len(parts) != 4:
            return
        try:
            t_ms = int(parts[1])
            raw = int(parts[2])
            v = float(parts[3])
        except:
            return

        t_s = t_ms / 1000.0
        est = self.cal.estimate_mm(v) if self.cal.ready else None

        # update live label always
        if est is None:
            self.lbl_live.setText(f"V={v:.5f}   raw={raw}   est_mm=-")
        else:
            self.lbl_live.setText(f"V={v:.5f}   raw={raw}   est_mm={est:.2f}")

        if self.capture_on:
            self.stream.append((t_s, raw, v))
            self.update_live_plot()

    def update_live_plot(self):
        if len(self.stream) < 2:
            return
        win = int(self.spin_window.value())
        t_end = self.stream[-1][0]
        xs = []
        ys = []
        for (t_s, raw, v) in reversed(self.stream):
            if (t_end - t_s) > win:
                break
            xs.append(t_s - t_end)  # negative seconds
            ys.append(v)
        xs.reverse(); ys.reverse()
        self.curve_live.setData(xs, ys)

    # ---------------- Calibration ----------------
    def last_avg_voltage(self, sec=0.25):
        """
        Average voltage over last 'sec' seconds from stream buffer.
        Requires capture_on and enough data.
        """
        if len(self.stream) < 5:
            return None
        t_end = self.stream[-1][0]
        vs = [v for (t_s, raw, v) in self.stream if (t_end - t_s) <= sec]
        if len(vs) < 3:
            return None
        return float(np.mean(vs))

    def add_cal_point(self):
        if not self.capture_on:
            QtWidgets.QMessageBox.information(self, "Capture", "Start Capture first to buffer data.")
            return
        v_avg = self.last_avg_voltage(sec=0.25)
        if v_avg is None:
            QtWidgets.QMessageBox.information(self, "Data", "Not enough recent samples.")
            return
        try:
            d = float(self.edit_true_mm.text())
        except:
            QtWidgets.QMessageBox.warning(self, "Distance", "Enter a numeric distance in mm.")
            return

        self.cal.add_point(v_avg, d)
        self.add_cal_row(v_avg, d)
        self.log(f"Cal point added: Vavg={v_avg:.6f} -> {d:.2f} mm")

        # update calibration scatter
        self.update_cal_plot(points_only=True)

    def add_cal_row(self, v, d):
        r = self.table_cal.rowCount()
        self.table_cal.insertRow(r)
        self.table_cal.setItem(r, 0, QtWidgets.QTableWidgetItem(f"{v:.6f}"))
        self.table_cal.setItem(r, 1, QtWidgets.QTableWidgetItem(f"{d:.2f}"))

    def clear_cal(self):
        self.cal.clear()
        self.table_cal.setRowCount(0)
        self.lbl_cal_state.setText("No interpolator")
        self.scatter_cal.setData([])
        self.curve_cal.setData([], [])
        self.log("Calibration cleared.")

    def build_calibrator(self):
        ok, msg = self.cal.build()
        self.lbl_cal_state.setText("Interpolator READY" if ok else "No interpolator")
        self.log(msg)
        self.update_cal_plot(points_only=False)

    def update_cal_plot(self, points_only=False):
        if len(self.cal.points) == 0:
            self.scatter_cal.setData([])
            self.curve_cal.setData([], [])
            return

        pts = np.array(self.cal.points, dtype=float)
        v = pts[:, 0]
        d = pts[:, 1]
        self.scatter_cal.setData(v, d)

        if points_only or not self.cal.ready:
            self.curve_cal.setData([], [])
            return

        # draw interpolated curve
        vs = self.cal._v_sorted
        ds = self.cal._d_sorted
        self.curve_cal.setData(vs, ds)

    # ---------------- Metrics ----------------
    def compute_repeatability(self):
        if not self.capture_on or len(self.stream) < 30:
            QtWidgets.QMessageBox.information(self, "Data", "Start Capture and collect a bit of data first.")
            return

        w = int(self.spin_rep_sec.value())
        t_end = self.stream[-1][0]
        window = [(t_s, v) for (t_s, raw, v) in self.stream if (t_end - t_s) <= w]
        if len(window) < 10:
            QtWidgets.QMessageBox.information(self, "Data", "Not enough samples in the selected window.")
            return

        vs = np.array([v for (t_s, v) in window], dtype=float)
        v_mean = float(np.mean(vs))
        v_std = float(np.std(vs))

        msg = f"Repeatability ({w}s): mean(V)={v_mean:.6f}, std(V)={v_std:.8f}"

        if self.cal.ready:
            ds = np.array([self.cal.estimate_mm(v) for v in vs], dtype=float)
            d_mean = float(np.mean(ds))
            d_std = float(np.std(ds))

            slope = self.cal.slope_dd_dv(v_mean)  # dd/dV
            if slope is None:
                res_est = None
            else:
                # resolution estimate based on voltage noise mapped to distance
                # Δd_min ≈ 2σ_v * |dd/dV|
                res_est = 2.0 * v_std * abs(slope)

            msg += f"\n             mean(mm)={d_mean:.3f}, std(mm)={d_std:.6f}"
            msg += f"\n             2σ(mm)={2*d_std:.6f}  (repeatability band ~ ±2σ)"
            if res_est is not None:
                msg += f"\n             Resolution est ≈ 2σ_v·|dd/dV| = {res_est:.6f} mm"
        else:
            msg += "\n             (Build interpolator to compute mm/std/resolution.)"

        self.log(msg)

    # ---------------- Accuracy test ----------------
    def add_accuracy_point(self):
        if not self.cal.ready:
            QtWidgets.QMessageBox.information(self, "Calibrator", "Build interpolator first.")
            return
        if len(self.stream) < 5:
            QtWidgets.QMessageBox.information(self, "Data", "No data yet.")
            return

        try:
            true_mm = float(self.edit_acc_true.text())
        except:
            QtWidgets.QMessageBox.warning(self, "True mm", "Enter numeric true distance (mm).")
            return

        v_avg = self.last_avg_voltage(sec=0.25)
        if v_avg is None:
            QtWidgets.QMessageBox.information(self, "Data", "Not enough recent samples.")
            return

        est = self.cal.estimate_mm(v_avg)
        self.acc_tests.append((true_mm, est, v_avg))
        self.update_accuracy_stats()
        self.log(f"Accuracy test added: true={true_mm:.2f} mm, est={est:.2f} mm, Vavg={v_avg:.6f}")

    def clear_accuracy(self):
        self.acc_tests = []
        self.lbl_acc.setText("No tests yet")
        self.log("Accuracy tests cleared.")

    def update_accuracy_stats(self):
        if not self.acc_tests:
            self.lbl_acc.setText("No tests yet")
            return
        arr = np.array(self.acc_tests, dtype=float)  # columns: true, est, v
        err = arr[:, 1] - arr[:, 0]
        rmse = float(np.sqrt(np.mean(err**2)))
        max_abs = float(np.max(np.abs(err)))
        mean_err = float(np.mean(err))
        self.lbl_acc.setText(f"Tests={len(err)} | mean_err={mean_err:+.3f} mm | RMSE={rmse:.3f} mm | max|err|={max_abs:.3f} mm")

    # ---------------- Export ----------------
    def export_stream_csv(self):
        if len(self.stream) == 0:
            QtWidgets.QMessageBox.information(self, "Stream", "No stream data.")
            return
        path, _ = QtWidgets.QFileDialog.getSaveFileName(self, "Save stream CSV", "stream.csv", "CSV (*.csv)")
        if not path:
            return
        with open(path, "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(["t_s", "raw_u16", "voltage_V"])
            for (t_s, raw, v) in self.stream:
                w.writerow([t_s, raw, v])
        self.log(f"Stream CSV saved: {path}")

    def export_cal_csv(self):
        if len(self.cal.points) == 0:
            QtWidgets.QMessageBox.information(self, "Cal", "No calibration points.")
            return
        path, _ = QtWidgets.QFileDialog.getSaveFileName(self, "Save calibration CSV", "calibration.csv", "CSV (*.csv)")
        if not path:
            return
        with open(path, "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(["voltage_V", "distance_mm"])
            for (v, d) in self.cal.points:
                w.writerow([v, d])
        self.log(f"Calibration CSV saved: {path}")

    def export_acc_csv(self):
        if len(self.acc_tests) == 0:
            QtWidgets.QMessageBox.information(self, "Accuracy", "No accuracy tests.")
            return
        path, _ = QtWidgets.QFileDialog.getSaveFileName(self, "Save accuracy CSV", "accuracy.csv", "CSV (*.csv)")
        if not path:
            return
        with open(path, "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(["true_mm", "est_mm", "error_mm", "voltage_V"])
            for (true_mm, est_mm, v) in self.acc_tests:
                w.writerow([true_mm, est_mm, est_mm-true_mm, v])
        self.log(f"Accuracy CSV saved: {path}")


def main():
    app = QtWidgets.QApplication(sys.argv)
    w = MainWindow()
    w.resize(1200, 720)
    w.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
