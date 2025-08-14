# -*- coding: utf-8 -*-

import os
import sys
from pathlib import Path
from subprocess import Popen

##############################################################################################################################

if __name__ == "__main__":
    currentDir = Path(sys.argv[0]).parent
    resourceDir = currentDir.as_posix()
    clientDir = Path(f'{resourceDir}{os.sep}src').as_posix()
    clientFile = Path(f'{clientDir}{os.sep}main.py').as_posix()
    configPath = currentDir.joinpath("config.json").as_posix()
    Popen(f'python "{clientFile}" --configPath "{configPath}"')

##############################################################################################################################

