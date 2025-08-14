from typing import Union, Optional
from PySide6.QtCore import Qt, QObject, Signal, QThreadPool, QPoint
from PySide6.QtWidgets import QWidget, QStackedWidget
from QEasyWidgets import QFunctions as QFunc, QWorker

##############################################################################################################################

def Function_AnimateStackedWidget(
    stackedWidget: QStackedWidget,
    target: Union[int, QWidget] = 0,
    duration: int = 99
):
    OriginalWidget = stackedWidget.currentWidget()
    OriginalGeometry = OriginalWidget.geometry()

    if isinstance(target, int):
        TargetIndex = target
    if isinstance(target, QWidget):
        TargetIndex = stackedWidget.indexOf(target)

    WidgetAnimation = QFunc.setWidgetPosAnimation(OriginalWidget, duration)
    WidgetAnimation.finished.connect(
        lambda: stackedWidget.setCurrentIndex(TargetIndex),
        type = Qt.QueuedConnection
    )
    WidgetAnimation.finished.connect(
        lambda: OriginalWidget.setGeometry(OriginalGeometry),
        type = Qt.QueuedConnection
    )
    WidgetAnimation.start() if stackedWidget.currentIndex() != TargetIndex else None

##############################################################################################################################

class WorkerManager(QWorker.WorkerManager):
    def __init__(self,
        executeMethod: object = ...,
        executeParams: Optional[dict] = None,
        terminateMethod: Optional[object] = None,
        autoDelete: bool = True,
        threadPool: Optional[QThreadPool] = None,
    ):
        super().__init__(executeMethod, terminateMethod, autoDelete, threadPool)

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