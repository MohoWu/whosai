import asyncio
import logging
from datetime import datetime

from whosai.application.ports import Clock, ScheduledCallback

logger = logging.getLogger(__name__)


class AsyncioScheduledJob:
    def __init__(self, task: asyncio.Task[None]) -> None:
        self._task = task

    def cancel(self) -> None:
        self._task.cancel()


class AsyncioTimerScheduler:
    """Run cancellable deadline callbacks on the active asyncio event loop."""

    def __init__(self, *, clock: Clock) -> None:
        self._clock = clock
        self._tasks: set[asyncio.Task[None]] = set()

    def schedule(
        self,
        *,
        deadline: datetime,
        callback: ScheduledCallback,
    ) -> AsyncioScheduledJob:
        if deadline.tzinfo is None:
            raise ValueError("Scheduled deadlines must include a timezone.")

        async def run() -> None:
            delay = max(0.0, (deadline - self._clock.now()).total_seconds())
            await asyncio.sleep(delay)
            await callback()

        task = asyncio.create_task(run())
        self._tasks.add(task)
        task.add_done_callback(self._task_finished)
        return AsyncioScheduledJob(task)

    def close(self) -> None:
        for task in tuple(self._tasks):
            task.cancel()

    def _task_finished(self, task: asyncio.Task[None]) -> None:
        self._tasks.discard(task)
        if task.cancelled():
            return
        error = task.exception()
        if error is not None:
            logger.error(
                "Scheduled callback failed",
                exc_info=(type(error), error, error.__traceback__),
            )
