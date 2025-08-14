import json
import os

##############################################################################################################################

class Config:
    _instance = None
    _default_config = {
        "parking_lot": {
            "total_spaces": 100,
            "hourly_rate": 5,
        },
        "gui": {
            "window_title": "停车场管理系统",
            "window_size": {
                "width": 800,
                "height": 600
            },
            "refresh_rate": 1000  # 界面刷新率（毫秒）
        },
        "data": {
            "records_file": "parking_records.csv"
        }
    }

    def __init__(self, config_path):
        """
        加载配置文件
        """
        self.config_path = config_path
        if os.path.exists(self.config_path):
            with open(self.config_path, 'r', encoding='utf-8') as f:
                self._config = json.load(f)
        else:
            self._config = self._default_config
            self._save_config()

    def _save_config(self):
        """
        保存配置到文件
        """
        os.makedirs(os.path.dirname(self.config_path), exist_ok=True)
        with open(self.config_path, 'w', encoding='utf-8') as f:
            json.dump(self._config, f, indent=4, ensure_ascii=False)

    def get(self, section, key=None):
        """
        获取配置项
        """
        if key is None:
            return self._config.get(section, {})
        return self._config.get(section, {}).get(key)

    def set(self, section, key, value):
        """
        设置配置项
        """
        if section not in self._config:
            self._config[section] = {}
        self._config[section][key] = value
        self._save_config()

    def get_parking_config(self):
        """
        获取停车场配置
        """
        return self.get('parking_lot')

    @property
    def total_spaces(self):
        return self.get('parking_lot', 'total_spaces')

    @property
    def hourly_rate(self):
        return self.get('parking_lot', 'hourly_rate')

    def get_gui_config(self):
        """
        获取GUI配置
        """
        return self.get('gui')

    def get_data_config(self):
        """
        获取数据存储配置
        """
        return self.get('data')

    @property
    def records_file(self):
        return os.path.join('data', self.get('data', 'records_file'))

    def get_model_paths(self):
        """
        获取模型路径
        """
        return self.get('models')

##############################################################################################################################

if __name__ == "__main__": # 使用示例
    # 测试配置加载和获取
    config = Config()
    print("停车场总车位:", config.total_spaces)
    print("每小时费率:", config.hourly_rate)
    # 测试配置修改
    config.set('parking_lot', 'total_spaces', 150)
    print("修改后的总车位:", config.total_spaces)

##############################################################################################################################