import time
from collections import deque
from dataclasses import dataclass, field


@dataclass
class User:
    id: int
    request_log: deque[float] = field(
        default_factory=deque
    )  # use default_factory for mutable defaults


# constants for 1 minute rolling window with 10 requests max per user
MAX_USER_REQUESTS = 10
WINDOW_SECONDS = 60


# utility function
def _resets_in(request_log: deque[float]) -> float:
    if not request_log:
        return 0.0
    return max(0.0, (request_log[0] + WINDOW_SECONDS) - time.time())


class Store:
    def __init__(self) -> None:
        self._users: dict[int, User] = {}
        self._next_id: int = 1

    def create_user(self) -> User:
        user = User(id=self._next_id)
        self._users[user.id] = user
        self._next_id += 1
        return user

    def get_user(self, user_id: int) -> User | None:
        return self._users.get(user_id)

    def get_quota(self, user: User) -> tuple[float, int]:
        current_time = time.time()
        # remove all requests older than 60 seconds from user request_log
        while user.request_log and user.request_log[0] < current_time - WINDOW_SECONDS:
            user.request_log.popleft()

        resets_in = _resets_in(user.request_log)
        remaining_slots = MAX_USER_REQUESTS - len(user.request_log)

        return (resets_in, remaining_slots)

    def record_request(self, user: User) -> tuple[bool, float, int]:
        # omit resets_in, will be recalculated after request made
        _, remaining_slots = self.get_quota(user)
        can_request = remaining_slots > 0

        if can_request:
            user.request_log.append(time.time())
            remaining_slots -= 1

        resets_in = _resets_in(user.request_log)

        return (can_request, resets_in, remaining_slots)


# create singleton
store = Store()
