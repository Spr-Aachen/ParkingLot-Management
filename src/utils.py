import os
import re
import math
import pandas as pd
from datetime import datetime, timedelta

from config import *

##############################################################################################################################

def check_path(path):
    if not os.path.exists(path):
        os.mkdir(path)


def check_url(img_url: str):
    """
    判断img_url路径是否含有中文字符
    :param img_url: 图片路径
    :return: True or False
    """
    result = re.search('[\u4e00-\u9fa5]', img_url)
    if result:
        return True
    else:
        return False

##############################################################################################################################

class ParkingLot:
    def __init__(self, configPath):
        self.config = Config(configPath)
        self.total_spaces = self.config.get('parking_lot', 'total_spaces')
        self.hourly_rate = self.config.get('parking_lot', 'hourly_rate')

        # 初始化可用车位数量
        self.available_spaces = self.total_spaces

        # 初始化闸门状态
        self.gate_status = "closed"

        # 创建数据目录
        os.makedirs('data', exist_ok=True)

        # 数据文件路径
        self.data_file = os.path.join('data', 'parking_records.csv')

        # 初始化或加载数据
        if os.path.exists(self.data_file):
            self.records = pd.read_csv(self.data_file)
            # 确保时间列的格式正确
            for col in ['Entry Time', 'Exit Time']:
                if col in self.records.columns:
                    self.records[col] = pd.to_datetime(self.records[col])
            # 更新可用车位
            current_parked = len(self.records[self.records['Exit Time'].isna()])
            self.available_spaces = self.total_spaces - current_parked
        else:
            self.records = pd.DataFrame(columns=[
                'License Plate', 'Entry Time', 'Exit Time', 'Fee'
            ])
            self._save_records()

    def update_prices(self, normal_price):
        """更新价格设置"""
        self.hourly_rate = normal_price
        self.config.set('parking_lot', 'hourly_rate', normal_price)
        self.config._save_config()

    def calculate_fee(self, entry_time, exit_time, plate):
        """计算停车费用
        Args:
            entry_time: 入场时间
            exit_time: 出场时间
            plate: 车牌号
        Returns:
            float: 停车费用
        """
        duration = (exit_time - entry_time).total_seconds() / 3600
        hours = math.ceil(duration)
        return round(hours * self.hourly_rate, 2)

    def _save_records(self):
        """保存记录到CSV文件"""
        os.makedirs(os.path.dirname(self.data_file), exist_ok=True)
        self.records.to_csv(self.data_file, index=False)
        # 保存价格到配置文件
        self.config.set('parking_lot', 'hourly_rate', self.hourly_rate)
        self.config._save_config()

    def validate_license_plate(self, plate):
        """验证车牌号格式"""
        pattern = r'^[京津沪渝冀豫云辽黑湘皖鲁新苏浙赣鄂桂甘晋蒙陕吉闽贵粤青藏川宁琼使领][A-Z][A-Z0-9]{5}$'
        return bool(re.match(pattern, plate))

    def check_duplicate_entry(self, plate):
        current_vehicles = self.records[self.records['Exit Time'].isna()]
        return plate in current_vehicles['License Plate'].values

    def get_parking_status(self):
        """获取停车场状态"""
        return {
            'total_spaces': self.total_spaces,
            'available_spaces': self.available_spaces,
            'gate_status': self.gate_status
        }

    def get_current_vehicles(self):
        """获取当前在场车辆"""
        return self.records[self.records['Exit Time'].isna()]

    def process_entry(self, plate):
        """处理车辆入场"""
        # if not self.validate_license_plate(plate):
        #     return False, "无效的车牌号"

        # 检查车位是否已满
        if self.available_spaces <= 0:
            return False, "停车场已满"

        # 检查车辆是否已在场内
        if len(self.records[
            (self.records['License Plate'] == plate) &
            (self.records['Exit Time'].isna())
        ]) > 0:
            return False, "该车辆已在停车场内"

        # 记录入场
        entry_time = datetime.now()
        new_record = pd.DataFrame({
            'License Plate': [plate],
            'Entry Time': [entry_time],
            'Exit Time': [pd.NA],
            'Fee': [0.0]
        })

        # 确保数据类型一致
        if len(self.records) > 0:
            new_record = new_record.astype(self.records.dtypes)

        self.records = pd.concat([self.records, new_record], ignore_index=True)
        self.available_spaces -= 1
        self._save_records()

        return True, f"车辆 {plate} 已成功入场"

    def process_exit(self, plate):
        """处理车辆出场"""
        # 查找未出场的记录
        current_record = self.records[
            (self.records['License Plate'] == plate) &
            (self.records['Exit Time'].isna())
        ]

        if len(current_record) == 0:
            return False, "未找到该车辆的入场记录"

        # 记录出场时间和计费
        exit_time = datetime.now()
        entry_time = current_record.iloc[0]['Entry Time']
        fee = self.calculate_fee(entry_time, exit_time, plate)

        # 更新记录
        self.records.loc[current_record.index, 'Exit Time'] = exit_time
        self.records.loc[current_record.index, 'Fee'] = fee
        self.available_spaces += 1
        self._save_records()

        return True, f"车辆 {plate} 已出场，费用：{fee}元"

    def get_records_by_date(self, date):
        """获取指定日期的记录，用于报表生成"""
        date_records = self.records[
            pd.to_datetime(self.records['Entry Time']).dt.date == date
        ]
        return date_records

    def get_records_by_date_range(self, start_date, end_date, plate=None):
        """获取指定日期范围内的记录
        Args:
            start_date: 开始日期
            end_date: 结束日期
            plate: 车牌号（可选）
        Returns:
            list: 符合条件的记录列表
        """
        # 转换日期为datetime
        start_datetime = pd.Timestamp(start_date)
        end_datetime = pd.Timestamp(end_date) + timedelta(days=1)  # 包含结束日期

        # 筛选日期范围内的记录
        mask = (pd.to_datetime(self.records['Entry Time']) >= start_datetime) & \
               (pd.to_datetime(self.records['Entry Time']) < end_datetime)

        if plate:
            # 如果指定了车牌号，添加车牌过滤条件
            mask = mask & (self.records['License Plate'] == plate)

        filtered_records = self.records[mask].copy()
        return filtered_records.to_dict('records')

##############################################################################################################################