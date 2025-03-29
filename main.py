# -*- coding: utf-8 -*-

import os
import sys
from pathlib import Path
from typing import Optional
from subprocess import Popen

##############################################################################################################################

# Get current directory
currentDir = Path(sys.argv[0]).parent


isCompiled = False


def run(
    configPath: str,
):
    resourceDir = Path(sys._MEIPASS).as_posix() if getattr(sys, 'frozen', None) else currentDir.as_posix()
    clientDir = Path(f'{resourceDir}{os.sep}src').as_posix()
    clientFile = Path(f'{clientDir}{os.sep}main.py').as_posix()
    clientCMD = f'python "{clientFile}" --configPath "{configPath}"'
    Popen(clientCMD)

##############################################################################################################################

if __name__ == "__main__":
    run(
        configPath = currentDir.joinpath("config.json").as_posix()
    )

##############################################################################################################################

