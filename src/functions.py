from typing import Union, Optional
from PySide6.QtCore import Qt, QObject, Signal, QThreadPool, QPoint
from QEasyWidgets import QFunctions as QFunc, QWorker

##############################################################################################################################

class WorkerManager(QWorker.WorkerManager):
    def __init__(self,
        executeMethod: object = ...,
        executeParams: Optional[dict] = None,
        terminateMethod: Optional[object] = None,
        threadPool: Optional[QThreadPool] = None,
    ):
        super().__init__(executeMethod, terminateMethod, threadPool)

        self.executeMethodName = executeMethod.__qualname__
        self.executeParams = executeParams

        self.signals = QWorker.WorkerSignals()
        self.worker.signals.started.connect(self.signals.started.emit)
        self.worker.signals.result.connect(self.signals.result.emit)
        self.worker.signals.finished.connect(self.signals.finished.emit)

    def execute(self):
        super().execute(*self.executeParams) if self.executeParams else super().execute()

    def terminate(self):
        super().terminate()

##############################################################################################################################