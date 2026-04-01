"""Entry point: python -m hea."""

import asyncio
import logging

from hea.bot.handlers import setup
from hea.settings import Settings

logger = logging.getLogger(__name__)


async def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    settings = Settings()
    dp, bot, repo, llm_client = await setup(settings)

    try:
        logger.info("Bot started. Polling...")
        await dp.start_polling(bot)
    finally:
        await repo.close()
        await llm_client.close()


if __name__ == "__main__":
    asyncio.run(main())
