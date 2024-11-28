import json

from utils.path_utils import get_path


class ConfigReader(object):

    def __init__(self, config_file):
        self._load(get_path(config_file))

    def _load(self, file):
        with open(file, "r") as file:
            self.data = json.load(file)

    def get(self, key=None):
        if key:
            return self.data[key]
        return self.data

    def print(self):
        print(self.data)