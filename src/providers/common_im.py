from src.providers.base import Provider
from src.core.client import get_lark_client


class IMProvider(Provider):
    def __init__(self):
        self.client = get_lark_client()

    async def send_text(self, receive_id_type, receive_id, content):
        # Implementation placeholder
        pass
