from .runtime import get_context

async def execute_command(minecraft_command:str) -> str:
    return (await get_context().client.command(
        "execute_command",
        {
            "command": minecraft_command
        }
    )).data["result"]