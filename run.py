"""
Точка входа для запуска приложения
Можно расширить для запуска ботов и других сервисов
"""
import sys
import logging
from server import app
import uvicorn
from config import HOST, PORT, DEBUG

logging.basicConfig(
    level=logging.INFO if not DEBUG else logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)

if __name__ == "__main__":
    logger.info(f"🔥 Starting HotSpot Shop on {HOST}:{PORT}")
    logger.info(f"📊 Debug mode: {DEBUG}")
    
    try:
        uvicorn.run(
            app,
            host=HOST,
            port=PORT,
            log_level="debug" if DEBUG else "info",
            access_log=True
        )
    except KeyboardInterrupt:
        logger.info("🛑 Shutting down...")
        sys.exit(0)
    except Exception as e:
        logger.error(f"❌ Fatal error: {e}", exc_info=True)
        sys.exit(1)

