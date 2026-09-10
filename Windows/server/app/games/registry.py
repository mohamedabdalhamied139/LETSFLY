from typing import Dict, Any, Callable, Coroutine
import asyncio

class ServerGamePlugin:
    def __init__(
        self,
        game_id: str,
        display_name: str,
        state_attr: str,
        start_handler: Callable,
        bot_runner: Callable = None,
        get_state_handler: Callable = None,
        action_handler: Callable = None,
        bot_replace_handler: Callable = None,
        stop_handler: Callable = None
    ):
        self.game_id = game_id
        self.display_name = display_name
        self.state_attr = state_attr
        self.start_handler = start_handler
        self.bot_runner = bot_runner
        self.get_state_handler = get_state_handler
        self.action_handler = action_handler
        self.bot_replace_handler = bot_replace_handler
        self.stop_handler = stop_handler

    def get_engine(self, room):
        return getattr(room, self.state_attr, None)

    def set_engine(self, room, engine):
        setattr(room, self.state_attr, engine)

REGISTRY: Dict[str, ServerGamePlugin] = {}

def register_plugin(plugin: ServerGamePlugin):
    REGISTRY[plugin.game_id] = plugin

def get_plugin(game_id: str) -> ServerGamePlugin:
    return REGISTRY.get(game_id)
