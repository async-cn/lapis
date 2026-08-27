from .runtime import get_context

async def execute_command(minecraft_command:str) -> str:
    """
    执行原版指令
    :param minecraft_command: 原版指令
    :return:
    """
    return (await get_context().client.command(
        "execute_command",
        {
            "command": minecraft_command
        }
    )).data["result"]