import sys
import argparse
import cv2
import pyttsx3
from pathlib import Path
from collections import Counter
from PySide6.QtWidgets import *
from PySide6.QtCore import Qt, QTimer, QSize, QTime, QThreadPool
from PySide6.QtGui import QImage, QPixmap, QFont

from utils import ParkingLot
from functions import WorkerManager
from core.yolo import YoloPredictor
from config import *

##############################################################################################################################

# 启动参数解析，启动环境，应用端口由命令行传入
parser = argparse.ArgumentParser()
parser.add_argument("--configPath", help = "配置路径", type = str, default = Path(currentDir).joinpath('config.json').as_posix())
args = parser.parse_args()

configPath = args.configPath

##############################################################################################################################

class MainWindow(QMainWindow):
    recognitionTime = 3000 # 计时器时长(ms)

    def __init__(self):
        super().__init__()

        self.threadPool = QThreadPool()

        self.parking_lot = ParkingLot(configPath)

        self.config = Config(configPath)

        # 从配置中获取模型路径
        model_paths = self.config.get_model_paths()
        self.detect_model_path = Path(configPath).parent.joinpath(model_paths['yolo_model']).as_posix()
        self.lprnet_model_path = Path(configPath).parent.joinpath(model_paths['lprnet_model']).as_posix()

        # 实例化yolo检测
        self.yolo_predict = YoloPredictor(self.lprnet_model_path)
        self.yolo_predict.new_model_name = self.detect_model_path
        # 显示预测视频
        #self.yolo_predict.yolo2main_trail_img.connect(lambda x: self.show_image(x, self.camera_label2))
        self.yolo_predict.yolo2main_box_img.connect(lambda x: self.show_image(x, self.camera_label))
        # 记录车牌信息
        self.yolo_predict.yolo2main_plate.connect(lambda x: self.recognized_plates.append(x))
        # 输出信息
        self.yolo_predict.yolo2main_status_msg.connect(lambda x: print("状态信息:", x))
        self.yolo_predict.yolo2main_fps.connect(lambda x: print("fps:", x))

        self.camera_active = False  # 添加摄像头状态标志

        # 设置定时器更新显示
        self.timer = QTimer()
        self.timer.timeout.connect(self.update_display)
        self.timer.start(self.config.get('gui', 'refresh_rate'))

        self.recognized_plates = []  # 存储识别到的车牌号
        self.recognition_timer = QTimer()  # 用于计时
        self.recognition_timer.timeout.connect(self.finalize_recognition)
        self.start_time = None

    #主窗口显示轨迹图像和检测图像 （缩放在这里）
    @staticmethod
    def show_image(img_src, label):
        try:
            # 检查图像的通道数，确定图像是否为彩色图像
            if len(img_src.shape) == 3:
                ih, iw, _ = img_src.shape
            if len(img_src.shape) == 2:
                ih, iw = img_src.shape
            # 根据标签窗口的大小调整图像的大小
            w = label.geometry().width()
            h = label.geometry().height()
            # 根据图像宽高比例进行缩放
            if iw / w > ih / h:
                scal = w / iw
                nw = w
                nh = int(scal * ih)
                img_src_ = cv2.resize(img_src, (nw, nh))
            else:
                scal = h / ih
                nw = int(scal * iw)
                nh = h
                img_src_ = cv2.resize(img_src, (nw, nh))
            # 将OpenCV图像从BGR格式转换为RGB格式，并创建QImage对象
            frame = cv2.cvtColor(img_src_, cv2.COLOR_BGR2RGB)
            img = QImage(frame.data, frame.shape[1], frame.shape[0], frame.shape[2] * frame.shape[1],
                         QImage.Format_RGB888)
            # 在标签窗口中显示图像
            label.setPixmap(QPixmap.fromImage(img))
        except Exception as e:
            print(repr(e))

    def toggle_camera(self):
        """切换摄像头状态"""
        if not self.camera_active:
            # 初始化摄像头
            name, _ = QFileDialog.getOpenFileName(self, 'Video/image', filter = "Pic File(*.mp4 *.mkv *.avi *.flv *.jpg *.png)")
            if not name:
                return
            # 设置线程
            self.worker_yolo_predict = WorkerManager(
                executeMethod = self.yolo_predict.run,
                terminateMethod = self.yolo_predict.terminate,
                threadPool = self.threadPool,
            )
            self.yolo_predict.source = name
            # 开始检测
            self.worker_yolo_predict.execute()
            # 开启摄像头
            self.camera_active = True
            self.camera_button.setText("关闭摄像头")
            # 计时
            self.recognition_timer.start(self.recognitionTime)
            self.start_time = QTime.currentTime()
        else:
            # 关闭摄像头
            self.camera_active = False
            self.recognition_timer.stop()
            self.worker_yolo_predict.terminate()
            self.camera_button.setText("开启摄像头")
            self.camera_label.clear()
            self.recognized_plates.clear()

    def finalize_recognition(self):
        """在若干秒后处理识别结果"""
        if self.recognized_plates:
            # 选择出现次数最多的车牌号
            most_common_plate = Counter(self.recognized_plates).most_common(1)[0][0]
            self.recognized_plates.clear() # 重置计数
            self.plate_input.setText(most_common_plate)

    def update_display(self):
        """更新显示信息"""
        # 更新状态标签
        status = self.parking_lot.get_parking_status()
        self.total_spaces_label.setText(f"总车位：{status['total_spaces']}")
        self.available_spaces_label.setText(f"可用车位：{status['available_spaces']}")

        # 更新在场车辆表格
        current_vehicles = self.parking_lot.get_current_vehicles()
        self.vehicles_table.setRowCount(len(current_vehicles))
        for i, (_, vehicle) in enumerate(current_vehicles.iterrows()):
            self.vehicles_table.setItem(i, 0, QTableWidgetItem(vehicle['License Plate']))
            self.vehicles_table.setItem(i, 1, QTableWidgetItem(str(vehicle['Entry Time'])))

    def speak(self, text):
        """播报文本信息"""
        engine = pyttsx3.init()
        engine.say(text)
        engine.runAndWait()

    def handle_entry(self):
        """处理车辆入场"""
        plate = self.plate_input.text().strip()
        if not plate:
            QMessageBox.warning(self, "警告", "请输入车牌号")
            return

        success, message = self.parking_lot.process_entry(plate)
        if success:
            QMessageBox.information(self, "成功", message)
            self.plate_input.clear()
            self.speak(f"{plate} 欢迎入场")  # 播报入场信息
        else:
            QMessageBox.warning(self, "失败", message)
        self.update_display()

    def handle_exit(self):
        """处理车辆出场"""
        plate = self.plate_input.text().strip()
        if not plate:
            QMessageBox.warning(self, "警告", "请输入车牌号")
            return

        success, message = self.parking_lot.process_exit(plate)
        if success:
            QMessageBox.information(self, "成功", message)
            self.plate_input.clear()
            self.speak(f"{plate} 一路顺风")  # 播报出场信息
        else:
            QMessageBox.warning(self, "失败", message)
        self.update_display()

    def show_message(self, message, success=True):
        """显示消息框"""
        QMessageBox.information(self, "提示", message) if success else \
        QMessageBox.warning(self, "警告", message)

    def main(self):
        # 设置窗口基本属性
        self.setWindowTitle("智能停车场管理系统")
        self.setMinimumSize(1200, 800)

        # 创建中心部件
        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        # 创建布局
        main_layout = QHBoxLayout(central_widget)

        # 左侧面板（状态和操作区）
        leftPanel = QFrame()
        leftPanel.setFrameStyle(QFrame.StyledPanel)
        layout = QVBoxLayout(leftPanel)
        layout.setSpacing(20)
        # 状态显示区域
        status_group = QGroupBox("停车场状态")
        status_group.setStyleSheet("""
            QGroupBox {
                font-weight: bold;
                border: 2px solid #cccccc;
                border-radius: 6px;
                margin-top: 6px;
                padding-top: 10px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px 0 5px;
            }
        """)
        status_layout = QVBoxLayout()
        # 使用大字体显示状态
        font = QFont()
        font.setPointSize(16)
        self.total_spaces_label = QLabel(f"总车位：{self.parking_lot.total_spaces}")
        self.available_spaces_label = QLabel(f"可用车位：{self.parking_lot.available_spaces}")
        self.total_spaces_label.setFont(font)
        self.available_spaces_label.setFont(font)
        status_layout.addWidget(self.total_spaces_label)
        status_layout.addWidget(self.available_spaces_label)
        status_group.setLayout(status_layout)
        layout.addWidget(status_group)
        # 车牌输入区域
        input_group = QGroupBox("车牌输入")
        input_layout = QVBoxLayout()
        self.plate_input = QLineEdit()
        self.plate_input.setPlaceholderText("请输入车牌号或使用摄像头识别")
        self.plate_input.setMinimumHeight(40)
        self.plate_input.setFont(QFont("Arial", 12))
        input_layout.addWidget(self.plate_input)
        # 操作按钮区域
        button_layout = QHBoxLayout()
        self.entry_button = QPushButton("车辆入场")
        self.exit_button = QPushButton("车辆出场")
        # 连接按钮信号
        self.entry_button.clicked.connect(self.handle_entry)
        self.exit_button.clicked.connect(self.handle_exit)
        self.entry_button.setMinimumHeight(40)
        self.exit_button.setMinimumHeight(40)
        # 设置按钮样式
        button_style = """
            QPushButton {
                background-color: #2196F3;
                color: white;
                border-radius: 4px;
                font-weight: bold;
                font-size: 14px;
            }
            QPushButton:hover {
                background-color: #1976D2;
            }
            QPushButton:pressed {
                background-color: #0D47A1;
            }
        """
        self.entry_button.setStyleSheet(button_style)
        self.exit_button.setStyleSheet(button_style.replace("#2196F3", "#4CAF50").replace("#1976D2", "#388E3C").replace("#0D47A1", "#1B5E20"))
        button_layout.addWidget(self.entry_button)
        button_layout.addWidget(self.exit_button)
        input_layout.addLayout(button_layout)
        input_group.setLayout(input_layout)
        layout.addWidget(input_group)
        layout.addStretch() # 添加弹性空间
        main_layout.addWidget(leftPanel, 1)

        # 右侧面板（摄像头和车辆列表）
        rightPanel = QFrame()
        rightPanel.setFrameStyle(QFrame.StyledPanel)
        layout = QVBoxLayout(rightPanel)
        layout.setSpacing(20)
        # 摄像头区域
        camera_group = QGroupBox("车牌识别")
        camera_layout = QVBoxLayout()
        self.camera_label = QLabel()
        self.camera_label.setMinimumSize(640, 480)
        self.camera_label.setAlignment(Qt.AlignCenter)
        self.camera_label.setStyleSheet("""
            QLabel {
                border: 2px solid #cccccc;
                border-radius: 4px;
                background-color: #f5f5f5;
            }
        """)
        camera_layout.addWidget(self.camera_label)
        self.camera_button = QPushButton("开启摄像头")
        self.camera_button.clicked.connect(self.toggle_camera)
        self.camera_button.setMinimumHeight(40)
        self.camera_button.setStyleSheet("""
            QPushButton {
                background-color: #FF5722;
                color: white;
                border-radius: 4px;
                font-weight: bold;
                font-size: 14px;
            }
            QPushButton:hover {
                background-color: #F4511E;
            }
            QPushButton:pressed {
                background-color: #D84315;
            }
        """)
        camera_layout.addWidget(self.camera_button)
        camera_group.setLayout(camera_layout)
        layout.addWidget(camera_group)
        # 在场车辆列表
        vehicles_group = QGroupBox("在场车辆")
        vehicles_layout = QVBoxLayout()
        self.vehicles_table = QTableWidget()
        self.vehicles_table.setColumnCount(2)
        self.vehicles_table.setHorizontalHeaderLabels(["车牌号", "入场时间"])
        self.vehicles_table.horizontalHeader().setStretchLastSection(True)
        self.vehicles_table.setStyleSheet("""
            QTableWidget {
                border: none;
                gridline-color: #e0e0e0;
            }
            QHeaderView::section {
                background-color: #f5f5f5;
                padding: 6px;
                border: none;
                border-bottom: 2px solid #e0e0e0;
                font-weight: bold;
            }
        """)
        vehicles_layout.addWidget(self.vehicles_table)
        vehicles_group.setLayout(vehicles_layout)
        layout.addWidget(vehicles_group)
        main_layout.addWidget(rightPanel, 2)

        self.show()

##############################################################################################################################

if __name__ == '__main__':
    App = QApplication(sys.argv)

    window = MainWindow()
    window.main()

    sys.exit(App.exec())

##############################################################################################################################