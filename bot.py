import nonebot

from nonebot.adapters.onebot.v11 import Adapter as OneBotV11Adapter
from nonebot import get_driver

# 初始化
nonebot.init()

driver = get_driver()
driver.register_adapter(OneBotV11Adapter)

# 自动加载 ml_bot/plugins 目录下的所有插件
nonebot.load_plugins("ml_bot/plugins")

if __name__ == "__main__":
    nonebot.run()
