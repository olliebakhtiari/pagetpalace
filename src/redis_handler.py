# Python standard.
import json

# Third-party.
import redis

# Local.
from ..tools.logger import *


class RedisHandler:
    local: bool
    redis_store: redis.Redis

    def __init__(self, local: bool):
        self.local = local

    def _connect_to_redis(self):
        try:
            return redis.Redis(
                # TODO: setup elasticache.
                host='127.0.0.1' if self.local else 'SETUP ELASTICACHE.',
                port=6379,
                db=0,
                password='',
                encoding='utf-8',
                single_connection_client=False,
                retry_on_timeout=False,
            )
        except Exception as exc:
            logger.error(f'Failed to connect to Redis. {exc}', exc_info=True)
            raise ConnectionError

    def __enter__(self):
        self.redis_store = self._connect_to_redis()

        return self

    def __exit__(self, *exc):
        self.redis_store.close()

        return False

    # TODO: implement required operations
    #       - track which strat has which orders by looking at order ids.
    #       - track previous entry signals.

