from typing import Callable, Any, Dict

class ClientGameAdapter:
    def __init__(
        self, 
        game_id: str, 
        display_name: str, 
        get_settings: Callable,
        apply_state: Callable,
        setup_ui: Callable = None,
        handle_key: Callable = None,
        focus_initial: Callable = None,
        clear_hand: Callable = None,
        poll_state: Callable = None,
        get_first_widget: Callable = None
    ):
        self.game_id = game_id
        self.display_name = display_name
        self.get_settings = get_settings
        self.apply_state = apply_state
        self.setup_ui = setup_ui
        self.handle_key = handle_key
        self.focus_initial = focus_initial
        self.clear_hand = clear_hand
        self.poll_state = poll_state
        self.get_first_widget = get_first_widget

REGISTRY: Dict[str, ClientGameAdapter] = {}

def register_adapter(adapter: ClientGameAdapter):
    REGISTRY[adapter.game_id] = adapter

def get_adapter(game_id: str) -> ClientGameAdapter:
    return REGISTRY.get(game_id)
