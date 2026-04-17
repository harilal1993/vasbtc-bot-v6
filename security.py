from __future__ import annotations
import os
import time
from collections import defaultdict, deque

class SimpleSecurity:
    def __init__(self) -> None:
        admin = os.getenv("TELEGRAM_ADMIN_USER_ID", "").strip()
        self.admin_user_id = int(admin) if admin.isdigit() else None
        self.calls = defaultdict(deque)

    def is_admin(self, user_id: int | None) -> bool:
        if self.admin_user_id is None:
            return True
        return user_id == self.admin_user_id

    def rate_limit_ok(self, user_id: int | None, limit: int = 20, window: int = 30) -> bool:
        if user_id is None:
            return False
        now = time.time()
        q = self.calls[user_id]
        while q and now - q[0] > window:
            q.popleft()
        if len(q) >= limit:
            return False
        q.append(now)
        return True
