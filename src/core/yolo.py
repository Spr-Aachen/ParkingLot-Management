# -*- coding: utf-8 -*-

import numpy as np
import time
import cv2
import supervision as sv
from ultralytics import YOLO
from ultralytics.engine.predictor import BasePredictor
from ultralytics.utils import DEFAULT_CFG, SETTINGS
from ultralytics.utils.torch_utils import smart_inference_mode
from ultralytics.cfg import get_cfg
from ultralytics.utils.checks import check_imshow
from PySide6.QtCore import Signal, QObject

from .lprr import CHARS
from .lprr.plate import de_lpr
from .paint_trail import draw_trail


class YoloPredictor(BasePredictor, QObject):
    yolo2main_plate = Signal(str)  # 车牌信息
    yolo2main_trail_img = Signal(np.ndarray)  # 轨迹图像信号
    yolo2main_box_img = Signal(np.ndarray)  # 绘制了标签与锚框的图像的信号
    yolo2main_status_msg = Signal(str)  # 检测/暂停/停止/测试完成等信号
    yolo2main_fps = Signal(str)  # fps
    yolo2main_labels = Signal(dict)  # 检测到的目标结果（每个类别的数量）
    yolo2main_progress = Signal(int)  # 进度条
    yolo2main_class_num = Signal(int)  # 当前帧类别数

    def __init__(self, lprnetModelPath, cfg=DEFAULT_CFG, overrides=None):
        super(YoloPredictor, self).__init__()
        QObject.__init__(self)

        self.lprnetModelPath = lprnetModelPath

        try:
            self.args = get_cfg(cfg, overrides)
        except:
            pass
        if self.args.show:
            self.args.show = check_imshow(warn=True)

        # GUI args
        self.used_model_name = None  # 使用过的检测模型名称
        self.new_model_name = None  # 新更改的模型

        self.source = ''  # 输入源str
        self.progress_value = 0  # 进度条的值

        self.terminate_dtc = False  # 终止bool
        self.suspend_dtc = False  # 暂停bool

        # config
        self.iou_thres = 0.45  # iou
        self.conf_thres = 0.25  # conf

        self.show_labels = True  # 显示图像标签bool
        self.show_trace = True  # 显示图像轨迹bool

        # 运行时候的参数放这里
        self.start_time = 0  # 拿来算FPS的计数变量
        self.count = 0
        self.class_num = 0
        self.total_frames = 0
        self.lock_id = 0

        # 设置线条样式    厚度 & 缩放大小
        self.box_annotator = sv.BoxAnnotator(
            thickness=2,
        )

    def emit_res(self, img_trail, img_box):
        """信号发送"""
        # 轨迹图像
        self.yolo2main_trail_img.emit(img_trail)
        # 标签图
        self.yolo2main_box_img.emit(img_box)
        # 总类别数量
        self.yolo2main_class_num.emit(self.class_num)
        # 进度条
        if '0' in self.source or 'rtsp' in self.source:
            self.yolo2main_progress.emit(0)
        else:
            self.progress_value = int(self.count / self.total_frames * 1000)
            self.yolo2main_progress.emit(self.progress_value)
        # FPS
        self.count += 1
        if self.count % 3 == 0 and self.count >= 3:  # 计算FPS
            self.yolo2main_fps.emit(str(int(3 / (time.time() - self.start_time))))
            self.start_time = time.time()

    def single_object_tracking(self, detections, img_box):
        """单目标跟踪"""
        store_xyxy_for_id = {}
        for xyxy, id in zip(detections.xyxy, detections.tracker_id):
            store_xyxy_for_id[id] = xyxy
            mask = np.zeros_like(img_box)
        try:
            if self.lock_id not in detections.tracker_id:
                cv2.destroyAllWindows()
                self.lock_id = None
            x1, y1, x2, y2 = int(store_xyxy_for_id[self.lock_id][0]), int(store_xyxy_for_id[self.lock_id][1]), int(
                store_xyxy_for_id[self.lock_id][2]), int(store_xyxy_for_id[self.lock_id][3])
            cv2.rectangle(mask, (x1, y1), (x2, y2), (255, 255, 255), -1)
            result_mask = cv2.bitwise_and(img_box, mask)
            result_cropped = result_mask[y1:y2, x1:x2]
            result_cropped = cv2.resize(result_cropped, (256, 256))
            return result_cropped

        except:
            cv2.destroyAllWindows()

    def open_target_tracking(self, detections, img_res):
        """单目标检测窗口开启"""
        try:
            # 单目标追踪
            result_cropped = self.single_object_tracking(detections, img_res)
            # print(result_cropped)
            cv2.imshow(f'OBJECT-ID:{self.lock_id}', result_cropped)
            cv2.moveWindow(f'OBJECT-ID:{self.lock_id}', 0, 0)
            # press esc to quit
            if cv2.waitKey(5) & 0xFF == 27:
                self.lock_id = None
                cv2.destroyAllWindows()
        except:
            cv2.destroyAllWindows()

    def res_address(self, img_res, result, height, width, model):
        """进行识别——并返回所有结果"""
        # 复制一份
        img_box = np.copy(img_res)   # 右边的图（会绘制标签！） img_res是原图-不会受影响
        img_trail = np.copy(img_res) # 左边的图
        # 如果没有识别的：
        if result.boxes.id is None:
            # 目标都是0
            self.class_num = 0
            print("暂未识别到目标！")
        # 如果有识别的
        else:
            detections = sv.Detections.from_yolov8(result)
            detections.tracker_id = result.boxes.id.cpu().numpy().astype(int)
            # id 、位置、目标总数
            self.class_num = self.get_class_number(detections)  # 类别数
            id = detections.tracker_id  # id
            xyxy = detections.xyxy  # 位置
            # 轨迹绘制部分
            if self.show_trace:
                img_trail = np.zeros((height, width, 3), dtype='uint8')  # 黑布
                identities = id
                grid_color = (255, 255, 255)
                line_width = 1
                grid_size = 100
                for y in range(0, height, grid_size):
                    cv2.line(img_trail, (0, y), (width, y), grid_color, line_width)
                for x in range(0, width, grid_size):
                    cv2.line(img_trail, (x, 0), (x, height), grid_color, line_width)
                draw_trail(img_trail, xyxy, model.model.names, id, identities)
            else:
                img_trail = img_res  # 显示原图
            # 画标签到图像上（并返回要写下的信息
            labels_write, img_box = self.creat_labels(detections, img_box, model)
            print("识别到目标\n%s" % labels_write)
        # 抠锚框里的图  （单目标追踪）
        if self.lock_id is not None:
            self.lock_id = int(self.lock_id)
            self.open_target_tracking(detections=detections, img_res=img_res)
        # 传递信号给主窗口
        self.emit_res(img_trail, img_box)

    @smart_inference_mode()  # 一个修饰器，用来开启检测模式：如果torch>=1.9.0，则执行torch.inference_mode()，否则执行torch.no_grad()
    def run(self):
        """点击开始检测按钮后的检测事件"""
        self.count = 0                 # 拿来参与算FPS的计数变量
        self.start_time = time.time()  # 拿来算FPS的计数变量
        # 加载模型
        self.yolo2main_status_msg.emit('正在加载模型...')
        if self.used_model_name != self.new_model_name:
            self.setup_model(self.new_model_name)
            self.used_model_name = self.new_model_name
        model = YOLO(self.new_model_name)
        # 检测
        if not ('mp4' in self.source or 'avi' in self.source or 'mkv' in self.source or 'flv' in self.source or 'mov' in self.source):
            return
        self.yolo2main_status_msg.emit('检测中...')
        # 使用OpenCV读取视频以获取进度条
        cap = cv2.VideoCapture(self.source)
        self.total_frames = cap.get(cv2.CAP_PROP_FRAME_COUNT)
        cap.release()
        # 开始检测
        iterModel = iter(
            model.track(
                source = self.source,
                stream = True,
                iou = self.iou_thres,
                conf = self.conf_thres
            )
        )
        while self.terminate_dtc == False:
            if not self.suspend_dtc:
                result = iterModel.__next__()
                img_res = result.orig_img  # 原图
                height, width, _ = img_res.shape
                self.res_address(img_res, result, height, width, model)
        # 结束检测
        self.source = None
        self.yolo2main_status_msg.emit('检测终止')

    def creat_labels(self, detections, img_box, model):
        """画标签到图像上"""
        # 画车牌
        label_plate = []
        # 确保xyxy是二维数组 (n,4)
        xy_xy_list = np.atleast_2d(detections.xyxy.squeeze())
        class_id_list = detections.class_id.squeeze()
        # 确保class_id_list是一维数组
        if isinstance(class_id_list, np.ndarray):
            class_id_list = class_id_list.tolist()
        elif isinstance(class_id_list, (int, float)):
            class_id_list = [class_id_list]
        xyxy = []
        # 车牌获取
        for i in range(len(xy_xy_list)):
            # 检查当前class_id
            if isinstance(class_id_list, list) and i >= len(class_id_list):
                continue
            current_class = class_id_list[i] if isinstance(class_id_list, list) else class_id_list
            if current_class != 0:  # 只处理车牌类别(假设0是车牌)
                continue
            xy_xy_filter = xy_xy_list[i]
            xyxy.append(xy_xy_filter)
            plate = de_lpr(xy_xy_filter, img_box, self.lprnetModelPath)
            plate = np.array(plate)
            car_number = ""
            for m in range(0, plate.shape[1]):
                # 将字符转换成车牌号码
                b = CHARS[plate[0][m]]
                car_number += b
            label_plate.append(car_number)
            self.yolo2main_plate.emit(car_number)
        # 修改坐标数组
        if xyxy:  # 如果有车牌检测结果
            detections.xyxy = np.array(xyxy)
        else:
            detections.xyxy = np.empty((0, 4))  # 返回空数组保持维度
        # 要画出来的信息
        labels_draw = label_plate
        # 存储labels里的信息
        labels_write = [
            f"目标ID: {tracker_id} 目标类别: {class_id} 置信度: {confidence:0.2f}"
            for _, _, confidence, class_id, tracker_id in detections
        ]
        # 如果显示标签 （要有才可以画呀！）---否则就是原图
        if (self.show_labels is True) and (self.class_num != 0) and len(detections.xyxy) > 0:
            img_box = self.box_annotator.annotate(scene=img_box, detections=detections, labels=labels_draw)
        return labels_write, img_box

    def get_class_number(self, detections):
        """获取类别数"""
        self.class_num = 0
        # 只识别车牌：则结果恒为1
        return 1
        # class_num_arr = []
        # for each in detections.class_id:
        #     if each not in class_num_arr :
        #         class_num_arr.append(each)
        # return len(class_num_arr)

    def terminate(self):
        """终止"""
        self.terminate_dtc = True