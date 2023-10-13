import aiohttp


class ActionLogClient:
    def __init__(self) -> None:
        self.timeout = aiohttp.ClientTimeout(total=10)

    async def create_action_log(self, data: dict, url: str):
        try:
            async with aiohttp.ClientSession(timeout=self.timeout) as session:
                async with session.post(
                    url,
                    json=data,
                    ssl=False,
                ) as response:
                    await response.json()
                    return True
        except Exception as err:
            print("Exception --> ", err)
            return True
