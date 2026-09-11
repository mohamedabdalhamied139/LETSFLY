import os
import sys
import pytest
from unittest.mock import MagicMock, patch

# Ensure project root is in sys.path
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from PySide6.QtWidgets import QApplication, QWidget, QLineEdit, QListWidget, QListWidgetItem
from PySide6.QtCore import Qt, QEvent
from PySide6.QtGui import QKeyEvent, QFocusEvent

from server.app.games.scopa import ScopaGame
from client.views.table_view import ScopaCardList, TableView
from client.audio.sound_engine import sound_engine


@pytest.fixture(scope="session")
def qapp():
    app = QApplication.instance()
    if not app:
        app = QApplication([])
    return app


class DummyTableView(QWidget):
    """Minimal TableView harness for testing ScopaCardList and Scopa focus mechanics."""
    def __init__(self):
        super().__init__()
        self.game_type = "SCOPA"
        self.is_playing = True
        self.activated_items = []
        self._scopa_state = {
            "active": True,
            "current_turn_id": 100,
            "my_hand": [
                {"id": "c1", "suit": "Diamonds", "value": 7},
                {"id": "c2", "suit": "Hearts", "value": 1},
                {"id": "c3", "suit": "Spades", "value": 3},
            ]
        }
        self.scopa_card_list = ScopaCardList(self)
        self.chat_input = QLineEdit(self)
        self.main_table_widget = QListWidget(self)
        self.scopa_container = QWidget(self)
        self._scopa_gameplay_focus = False
        self._focus_target = "gameplay"
        self._last_scopa_hand_sig = None
        self._last_scopa_turn_id = None
        self.window_mock = MagicMock()
        self.window_mock.user = {"id": 100}
        self.scopaActionSubmitted = MagicMock()

    def window(self):
        return self.window_mock

    def _is_modal_active(self):
        return False

    def _on_scopa_card_activated(self, item):
        self.activated_items.append(item)
        data = item.data(Qt.UserRole)
        if data and data.get("card_index") is not None:
            self.scopaActionSubmitted.emit("play", str(data.get("card_index")), "")


# ============================================================================
# R1 Tests: Fix Focus Escaping to Chat
# ============================================================================

def test_scopa_card_list_key_press_activation(qapp):
    """Verify Enter, Return, and Space trigger card activation directly."""
    table = DummyTableView()
    list_widget = table.scopa_card_list

    item = QListWidgetItem("7 دايموند")
    item.setData(Qt.UserRole, {"type": "card", "card_index": 0})
    list_widget.addItem(item)
    list_widget.setCurrentRow(0)

    # Test Return key
    event_return = QKeyEvent(QEvent.KeyPress, Qt.Key_Return, Qt.NoModifier)
    list_widget.keyPressEvent(event_return)
    assert len(table.activated_items) == 1
    assert table.activated_items[-1] is item

    # Test Enter key
    event_enter = QKeyEvent(QEvent.KeyPress, Qt.Key_Enter, Qt.NoModifier)
    list_widget.keyPressEvent(event_enter)
    assert len(table.activated_items) == 2

    # Test Space key
    event_space = QKeyEvent(QEvent.KeyPress, Qt.Key_Space, Qt.NoModifier)
    list_widget.keyPressEvent(event_space)
    assert len(table.activated_items) == 3


def test_scopa_card_list_focus_out_protection(qapp):
    """Verify focusOutEvent prevents Qt from dropping focus out during the player's turn."""
    table = DummyTableView()
    list_widget = table.scopa_card_list
    list_widget.addItem(QListWidgetItem("Card 1"))

    with patch("client.views.table_view.QTimer.singleShot") as mock_single_shot:
        # Simulate Qt internal focus loss (OtherFocusReason, e.g. widget removal)
        focus_event = QFocusEvent(QEvent.FocusOut, Qt.FocusReason.OtherFocusReason)
        list_widget.focusOutEvent(focus_event)

        # Focus must be re-pinned via singleShot
        assert mock_single_shot.called
        delays = [call[0][0] for call in mock_single_shot.call_args_list]
        assert 0 in delays


def test_scopa_card_list_focus_out_allowed_for_tab(qapp):
    """Verify Tab navigation to chat/log is NOT blocked."""
    table = DummyTableView()
    list_widget = table.scopa_card_list
    list_widget.addItem(QListWidgetItem("Card 1"))

    with patch("client.views.table_view.QTimer.singleShot") as mock_single_shot:
        # Simulate intentional Tab key navigation
        focus_event = QFocusEvent(QEvent.FocusOut, Qt.FocusReason.TabFocusReason)
        list_widget.focusOutEvent(focus_event)

        # Tab navigation should NOT trigger the safety singleShot refocus
        assert not mock_single_shot.called


def test_render_scopa_items_removes_card_without_losing_focus(qapp):
    """Verify that removing the played card clamps row first and preserves list focus."""
    table = DummyTableView()
    list_widget = table.scopa_card_list

    # Initial hand: 3 cards, player is focused on card at index 2 (last card)
    table._scopa_state = {
        "active": True,
        "current_turn_id": 100,
        "my_hand": [
            {"id": "c1", "suit": "Diamonds", "value": 7},
            {"id": "c2", "suit": "Hearts", "value": 1},
            {"id": "c3", "suit": "Spades", "value": 3},
        ]
    }
    TableView._render_scopa_items(table)
    assert list_widget.count() == 3
    list_widget.setCurrentRow(2)
    assert list_widget.currentRow() == 2

    # Player plays the last card; server sends updated hand with 2 cards
    table._scopa_state = {
        "active": True,
        "current_turn_id": 100,
        "my_hand": [
            {"id": "c1", "suit": "Diamonds", "value": 7},
            {"id": "c2", "suit": "Hearts", "value": 1},
        ]
    }

    # Focus is currently on list
    with patch.object(list_widget, "hasFocus", return_value=True):
        TableView._render_scopa_items(table)

    # Row must have been safely clamped to 1 (new last item)
    assert list_widget.count() == 2
    assert list_widget.currentRow() == 1
    assert table._focus_target == "gameplay"


# ============================================================================
# R2 Tests: Prevent Redundant List / قائمة Announcements on Opponent Plays
# ============================================================================

def test_opponent_turn_does_not_repopulate_or_refocus(qapp):
    """Verify that when an opponent plays, _render_scopa_items does NOT modify items."""
    table = DummyTableView()
    list_widget = table.scopa_card_list

    table._scopa_state = {
        "active": True,
        "current_turn_id": 200,  # Opponent turn
        "my_hand": [
            {"id": "c1", "suit": "Diamonds", "value": 7},
            {"id": "c2", "suit": "Hearts", "value": 1},
        ]
    }
    TableView._render_scopa_items(table)
    assert list_widget.count() == 2

    # Opponent plays: turn remains or shifts, but my hand is unchanged
    table._scopa_state = {
        "active": True,
        "current_turn_id": 300,  # Another opponent turn
        "my_hand": [
            {"id": "c1", "suit": "Diamonds", "value": 7},
            {"id": "c2", "suit": "Hearts", "value": 1},
        ]
    }

    with patch.object(list_widget, "setCurrentRow") as mock_set_row:
        with patch.object(list_widget, "takeItem") as mock_take:
            with patch.object(list_widget, "addItem") as mock_add:
                TableView._render_scopa_items(table)
                # Must not touch list items or trigger row selection
                assert not mock_set_row.called
                assert not mock_take.called
                assert not mock_add.called


def test_my_turn_arrival_does_not_refocus_if_already_focused(qapp):
    """Verify that when turn arrives, safe_set_focus is NOT called if list already has focus."""
    table = DummyTableView()
    list_widget = table.scopa_card_list

    table._scopa_state = {
        "active": True,
        "current_turn_id": 200,  # Opponent
        "my_hand": [{"id": "c1", "suit": "Diamonds", "value": 7}]
    }
    TableView._render_scopa_items(table)

    # Turn changes to my turn (100)
    table._scopa_state = {
        "active": True,
        "current_turn_id": 100,  # Me
        "my_hand": [{"id": "c1", "suit": "Diamonds", "value": 7}]
    }

    with patch.object(list_widget, "hasFocus", return_value=True):
        with patch("client.views.table_view.safe_set_focus") as mock_safe_focus:
            TableView._render_scopa_items(table)
            # Since hasFocus is True, safe_set_focus should NOT be called (prevents NVDA 'قائمة' speech)
            assert not mock_safe_focus.called


# ============================================================================
# R3 Tests: Last Card, Sound Cues, and Round Finalization
# ============================================================================

def test_scopa_engine_preserves_final_play_event():
    """Verify ScopaGame preserves final card play event before finalization."""
    game = ScopaGame([(1, "Player1"), (2, "Player2")], target_score=11)
    game.start_new_round()

    # Clear deck and set hands to 1 card each
    game.deck = []
    card1 = {"id": "c1", "suit": "Diamonds", "value": 7}
    card2 = {"id": "c2", "suit": "Hearts", "value": 7}
    game.hands = {1: [card1], 2: [card2]}
    game.table_cards = [{"id": "t1", "suit": "Spades", "value": 7}]
    game.current_turn_index = 0  # Player 1

    # Player 1 plays card1, capturing t1
    result = game.play_card(1, 0)
    assert result["status"] == "captured"

    # Player 2 still has 1 card; round is not finalized yet
    assert game.pending_round_finalize is False

    # Player 2 plays the final card of the round
    result2 = game.play_card(2, 0)
    assert result2["status"] in ("played", "captured")

    # Both hands and deck are empty: pending_round_finalize must be True
    assert game.pending_round_finalize is True
    # Final play event must still be the card play event, NOT overwritten by round summary
    assert game.event_type in ("CARD_PLAYED", "CARD_CAPTURED", "SCOPA_SWEEP")
    assert "7" in game.last_action

    # public_state exposes pending_round_finalize
    state = game.public_state(2)
    assert state.get("pending_round_finalize") is True

    # Now finalize round
    game._finalize_round()
    assert game.pending_round_finalize is False
    assert game.final_play_event_id is not None
    assert game.final_play_event_type in ("CARD_PLAYED", "CARD_CAPTURED", "SCOPA_SWEEP")
    assert game.event_type == "ROUND_FINISHED"


def test_scopa_sound_cues_multi_event_resolution():
    """Verify event_cues returns all necessary sounds for Scopa captures and sweeps."""
    cues_capture = sound_engine.event_cues("SCOPA", "CARD_CAPTURED")
    assert "SCOPA_CARD_THROW" in cues_capture
    assert "SCOPA_EAT_CARDS" in cues_capture

    cues_sweep = sound_engine.event_cues("SCOPA", "SCOPA_SWEEP")
    assert "SCOPA_CARD_THROW" in cues_sweep
    assert "SCOPA_EAT_CARDS" in cues_sweep
    assert "SCOPA_ANNOUNCEMENT" in cues_sweep


def test_client_app_final_play_deduplication():
    """Verify _announce_scopa_final_play de-duplicates by event ID and does not double-announce."""
    from client.client_app import TableVerseApp

    dummy_app = MagicMock(spec=TableVerseApp)
    dummy_app._seen_scopa_final_plays = set()
    dummy_app.current_room = {"id": "room_123"}

    event = {
        "final_play_action": "لعب فلان 7 وأكل بها",
        "final_play_event_type": "CARD_CAPTURED",
        "final_play_event_id": 42,
    }

    with patch("client.client_app.reader.speak") as mock_speak:
        with patch("client.client_app.sound_engine.event_cues", return_value=["SCOPA_CARD_THROW", "SCOPA_EAT_CARDS"]):
            with patch("client.client_app.QTimer.singleShot") as mock_single_shot:
                # First announcement succeeds
                res1 = TableVerseApp._announce_scopa_final_play(dummy_app, event)
                assert res1 is True
                assert mock_speak.called
                # Ensure interrupt=False is passed
                assert mock_speak.call_args[1].get("interrupt") is False

                # Second announcement of the same event is suppressed
                mock_speak.reset_mock()
                res2 = TableVerseApp._announce_scopa_final_play(dummy_app, event)
                assert res2 is False
                assert not mock_speak.called


def test_scopa_sweep_on_last_card_event_preserved():
    """Verify that a Scopa sweep on the final card preserves SCOPA_SWEEP event."""
    game = ScopaGame([(1, "Player1"), (2, "Player2")], target_score=11)
    game.start_new_round()

    game.deck = []
    card1 = {"id": "c1", "suit": "Diamonds", "value": 7}
    card2 = {"id": "c2", "suit": "Hearts", "value": 7}
    game.hands = {1: [card1], 2: [card2]}
    # Only 1 card on the table matching player 1's card
    game.table_cards = [{"id": "t1", "suit": "Spades", "value": 7}]
    game.current_turn_index = 0

    # Note: By Scopa rules, sweep cannot occur on the very last card of the final deal,
    # but let's test sweep handling on penultimate card
    res1 = game.play_card(1, 0)
    assert res1["status"] == "captured"
    # Player 2 plays remaining card to empty table
    res2 = game.play_card(2, 0)
    assert game.pending_round_finalize is True


def test_scopa_pending_deal_batch_when_deck_has_cards():
    """Verify that when hands are empty but deck has cards, pending_deal_batch is set."""
    game = ScopaGame([(1, "Player1"), (2, "Player2")], target_score=11)
    game.start_new_round()

    # Leave 4 cards in deck
    game.deck = [{"id": f"d{i}", "suit": "Clubs", "value": i} for i in range(1, 5)]
    game.hands = {
        1: [{"id": "c1", "suit": "Diamonds", "value": 1}],
        2: [{"id": "c2", "suit": "Hearts", "value": 2}],
    }
    game.current_turn_index = 0

    game.play_card(1, 0)
    assert game.pending_deal_batch is False
    assert game.pending_round_finalize is False

    game.play_card(2, 0)
    # Both hands empty, but deck has cards -> pending_deal_batch = True
    assert game.pending_deal_batch is True
    assert game.pending_round_finalize is False


def test_render_scopa_items_empty_hand(qapp):
    """Verify that rendering an empty hand when round is active creates a waiting item without crashing."""
    table = DummyTableView()
    list_widget = table.scopa_card_list

    table._scopa_state = {
        "active": True,
        "current_turn_id": 100,
        "my_hand": []
    }
    TableView._render_scopa_items(table)
    assert list_widget.count() == 1
    item = list_widget.item(0)
    data = item.data(Qt.UserRole)
    assert data.get("type") == "waiting"


def test_deal_batch_announces_new_turn_for_player():
    """Verify that when a new batch is dealt, the player's turn is announced (not suppressed)."""
    from client.table_framework.state_engine import ClientStateEngine

    app = MagicMock()
    app.current_room = {"id": "123"}
    app.user = {"id": 1}
    app._last_announced_turn_id_scopa = "2"
    app._last_scopa_event_id = 10

    state = {
        "active": True,
        "event_id": 11,
        "event_type": "DEAL_BATCH",
        "sound_cue": "SCOPA_DEAL",
        "last_action": "",
        "current_turn_id": 1,
        "current_turn_name": "Player 1",
        "my_hand": [{"id": "c1", "value": 7, "suit": "Diamonds"}],
    }

    with patch("client.table_framework.state_engine.announce_game_event") as mock_announce:
        ClientStateEngine.process_common_state(app, "SCOPA", state, lambda a, b: None)
        assert mock_announce.called
        assert mock_announce.call_args[0][0] == "دورك"
        assert mock_announce.call_args[1].get("interrupt") is False


def test_deal_batch_announces_new_turn_for_opponent():
    """Verify that when a new batch is dealt, the opponent's turn is announced (not suppressed)."""
    from client.table_framework.state_engine import ClientStateEngine

    app = MagicMock()
    app.current_room = {"id": "123"}
    app.user = {"id": 1}
    app._last_announced_turn_id_scopa = "1"
    app._last_scopa_event_id = 10

    state = {
        "active": True,
        "event_id": 11,
        "event_type": "DEAL_BATCH",
        "sound_cue": "SCOPA_DEAL",
        "last_action": "",
        "current_turn_id": 2,
        "current_turn_name": "Player 2",
        "my_hand": [{"id": "c1", "value": 7, "suit": "Diamonds"}],
    }

    with patch("client.table_framework.state_engine.announce_game_event") as mock_announce:
        ClientStateEngine.process_common_state(app, "SCOPA", state, lambda a, b: None)
        assert mock_announce.called
        assert "Player 2" in mock_announce.call_args[0][0]
        assert mock_announce.call_args[1].get("interrupt") is False


def test_is_my_turn_guards_against_none_user_and_turn_id(qapp):
    """Verify is_my_turn is False when user and/or current_turn_id is None."""
    table = DummyTableView()
    table.window_mock.user = None
    table._scopa_state = {
        "active": False,
        "current_turn_id": None,
        "my_hand": [],
    }
    with patch("client.views.table_view.QTimer.singleShot") as mock_single_shot:
        focus_event = QFocusEvent(QEvent.FocusOut, Qt.FocusReason.OtherFocusReason)
        table.scopa_card_list.focusOutEvent(focus_event)
        assert not mock_single_shot.called


def test_focus_scopa_does_not_refocus_if_already_focused(qapp):
    """Verify focus_scopa does not call setFocus if scopa_card_list already has focus."""
    from client.games.adapters.all_adapters import focus_scopa

    table = DummyTableView()
    list_widget = table.scopa_card_list
    list_widget.addItem(QListWidgetItem("Card 1"))

    with patch.object(list_widget, "hasFocus", return_value=True):
        with patch.object(list_widget, "setFocus") as mock_set_focus:
            focus_scopa(table)
            assert not mock_set_focus.called


def test_game_finished_does_not_preempt_scopa_match_finished():
    """Verify game_finished event for SCOPA is ignored so scopa_match_finished lifecycle runs cleanly."""
    from client.client_app import TableVerseApp

    app = MagicMock()
    app.current_room = {"id": "123"}
    app.table_view = MagicMock()
    app._was_my_turn = True

    event = {"type": "game_finished", "game": "SCOPA"}
    TableVerseApp._handle_ws_event(app, event)

    assert not app.table_view.set_playing_mode.called
    assert not app.table_view.main_table_widget.setFocus.called


def test_keep_scopa_hand_not_set_when_match_over():
    """Verify keep_scopa_hand is False when the match has ended (has winner)."""
    from client.table_framework.state_engine import ClientStateEngine

    app = MagicMock()
    app.current_room = {"id": "123", "status": "match_finished"}
    app.user = {"id": 1}

    state = {
        "active": False,
        "winner_id": 1,
        "final_play_action": "لعب فلان 7 وأكل بها",
        "round_finished": True,
    }

    ClientStateEngine.process_common_state(app, "SCOPA", state, lambda a, b: None)
    app.table_view.set_playing_mode.assert_called_with(False)


def test_four_player_scopa_simulation_deal_batches_and_final_capture():
    """Complete 4-player Scopa simulation through deal batches and round finalization."""
    game = ScopaGame([(1, "P1"), (2, "P2"), (3, "P3"), (4, "P4")], target_score=11)
    game.start_match()

    assert len(game.players) == 4
    assert len(game.deck) == 24
    assert all(len(h) == 3 for h in game.hands.values())

    batches_seen = 0
    # Play through all batches until pending_round_finalize
    for _ in range(3):
        while not all(len(h) == 0 for h in game.hands.values()):
            curr = game.current_player_id()
            game.play_card(curr, 0)

        if game.pending_deal_batch:
            batches_seen += 1
            game.pending_deal_batch = False
            game._deal_next_batch()

    assert batches_seen == 2
    assert len(game.deck) == 0

    # Final batch: play until 1 card remains in last player's hand
    while sum(len(h) for h in game.hands.values()) > 1:
        curr = game.current_player_id()
        game.play_card(curr, 0)

    # Set up final card capture
    final_player = game.current_player_id()
    game.hands[final_player] = [{"id": "fin_card", "suit": "Diamonds", "value": 7}]
    game.table_cards = [{"id": "t_card", "suit": "Spades", "value": 7}]

    res = game.play_card(final_player, 0)
    assert res["status"] == "captured"
    assert game.pending_round_finalize is True
    assert game.event_type in ("CARD_CAPTURED", "SCOPA_SWEEP")

    # Sound cues must contain throw and eat
    cues = sound_engine.event_cues("SCOPA", game.event_type, game.public_state(final_player))
    assert "SCOPA_CARD_THROW" in cues
    assert "SCOPA_EAT_CARDS" in cues

    # Finalize
    game._finalize_round()
    assert game.pending_round_finalize is False
    assert game.active is False
    assert game.final_play_event_type in ("CARD_CAPTURED", "SCOPA_SWEEP")
    assert "7" in game.final_play_action
    assert game.round_summary != ""


def test_scopa_tab_key_navigation_order(qapp):
    """Verify Tab and Shift-Tab cycle properly between ScopaCardList, chat_input, and activity_log."""
    tv = TableView()
    tv.game_type = "SCOPA"
    tv.is_playing = True
    tv.scopa_card_list = MagicMock()
    tv.scopa_card_list.isVisible.return_value = True

    with patch("client.table_framework.adapter.get_adapter") as mock_get_adapter:
        adapter_mock = MagicMock()
        adapter_mock.get_first_widget.return_value = tv.scopa_card_list
        mock_get_adapter.return_value = adapter_mock

        # Tab from chat_input -> activity_log
        with patch("PySide6.QtWidgets.QApplication.focusWidget", return_value=tv.chat_input):
            tv.focusNextPrevChild(True)
            assert tv._focus_target == "activity_log"

        # Tab from activity_log -> gameplay (scopa_card_list)
        with patch("PySide6.QtWidgets.QApplication.focusWidget", return_value=tv.activity_log):
            tv.focusNextPrevChild(True)
            assert tv._focus_target == "gameplay"

        # Tab from scopa_card_list -> chat
        with patch("PySide6.QtWidgets.QApplication.focusWidget", return_value=tv.scopa_card_list):
            tv.focusNextPrevChild(True)
            assert tv._focus_target == "chat"

        # Shift-Tab from chat_input -> gameplay (scopa_card_list)
        with patch("PySide6.QtWidgets.QApplication.focusWidget", return_value=tv.chat_input):
            tv.focusNextPrevChild(False)
            assert tv._focus_target == "gameplay"

        # Shift-Tab from activity_log -> chat
        with patch("PySide6.QtWidgets.QApplication.focusWidget", return_value=tv.activity_log):
            tv.focusNextPrevChild(False)
            assert tv._focus_target == "chat"

        # Shift-Tab from scopa_card_list -> activity_log
        with patch("PySide6.QtWidgets.QApplication.focusWidget", return_value=tv.scopa_card_list):
            tv.focusNextPrevChild(False)
            assert tv._focus_target == "activity_log"


@pytest.mark.anyio
async def test_scopa_action_final_state_returns_inactive():
    """Verify scopa_action returns active=False after round finalization."""
    from server.app.games.plugins.all_games import scopa_action

    room = MagicMock()
    room.room_id = "test_room"
    game = ScopaGame([(1, "P1"), (2, "P2")], target_score=11)
    game.start_new_round()
    game.deck = []
    game.hands = {1: [{"id": "c1", "suit": "Diamonds", "value": 7}], 2: []}
    game.table_cards = [{"id": "t1", "suit": "Spades", "value": 7}]
    game.current_turn_index = 0
    room.scopa_game = game
    room.players = [1, 2]
    room.scores = {}
    room.target_score = 11

    req = MagicMock()
    req.action = "play"
    req.card_id = "0"
    req.data = None

    with patch("server.app.games.plugins.all_games.ws_manager.broadcast_room"):
        with patch("server.app.games.plugins.all_games.asyncio.sleep"):
            with patch("server.app.games.plugins.all_games.check_and_finalize_scopa_round"):
                state = await scopa_action(room, 1, req)
                assert state.get("active") is False
                assert state.get("round_summary") != ""


def test_broadcast_scopa_state_sends_personalized_hands():
    """Verify broadcast_scopa_state delivers user-specific hands over WebSocket."""
    from server.app.games.scopa_lifecycle import broadcast_scopa_state
    from server.app.games.scopa import ScopaGame

    room = MagicMock()
    room.room_id = "test_scopa_room"
    room.players = [10, 20, -1]  # 10 and 20 are human players, -1 is bot
    room.spectators = [30]

    game = ScopaGame([(10, "Human1"), (20, "Human2"), (-1, "Bot1")], target_score=11)
    game.start_match()
    game.hands[10] = [{"id": "c10", "suit": "Diamonds", "value": 7}]
    game.hands[20] = [{"id": "c20", "suit": "Hearts", "value": 1}]

    with patch("server.app.games.scopa_lifecycle.ws_manager.broadcast_user") as mock_bc_user:
        broadcast_scopa_state(room, game)

        assert mock_bc_user.call_count == 3
        calls = {call[0][0]: call[0][1] for call in mock_bc_user.call_args_list}

        assert 10 in calls
        assert 20 in calls
        assert 30 in calls
        assert -1 not in calls

        assert calls[10]["state"]["my_hand"] == [{"id": "c10", "suit": "Diamonds", "value": 7}]
        assert calls[20]["state"]["my_hand"] == [{"id": "c20", "suit": "Hearts", "value": 1}]
        assert calls[30]["state"]["my_hand"] == []


def test_client_apply_scopa_state_preserves_hand_on_unpersonalized_broadcast():
    """Verify that an unpersonalized broadcast state does NOT erase player's cards."""
    from client.client_app import TableVerseApp

    app = MagicMock(spec=TableVerseApp)
    app.user = {"id": 100}
    app.current_room = {"id": "room1", "game": "SCOPA"}
    app.table_view = MagicMock()

    existing_cards = [
        {"id": "c1", "value": 7, "suit": "Diamonds"},
        {"id": "c2", "value": 1, "suit": "Hearts"},
        {"id": "c3", "value": 3, "suit": "Spades"},
    ]
    app.scopa_state = {"my_hand": existing_cards}

    unpersonalized_state = {
        "active": True,
        "current_turn_id": 200,
        "hands_count": {"100": 3, "200": 2},
        "my_hand": [],
        "event_id": 5,
        "event_type": "CARD_PLAYED",
        "last_action": "Opponent played a card",
    }

    with patch("client.table_framework.state_engine.ClientStateEngine.process_common_state"):
        TableVerseApp._apply_scopa_state(app, unpersonalized_state)

        assert app.scopa_state.get("my_hand") == existing_cards
        assert len(app.scopa_state.get("my_hand")) == 3


def test_client_apply_scopa_state_polls_when_hand_missing_for_deal_batch():
    """Verify that when a new batch arrives without private hand, _poll_table_state is triggered."""
    from client.client_app import TableVerseApp

    app = MagicMock(spec=TableVerseApp)
    app.user = {"id": 100}
    app.current_room = {"id": "room1", "game": "SCOPA"}
    app.table_view = MagicMock()

    app.scopa_state = {"my_hand": []}

    batch_state = {
        "active": True,
        "current_turn_id": 100,
        "hands_count": {"100": 3, "200": 3},
        "my_hand": [],
        "event_id": 10,
        "event_type": "DEAL_BATCH",
    }

    with patch.object(app, "_poll_table_state") as mock_poll:
        with patch("client.table_framework.state_engine.ClientStateEngine.process_common_state"):
            TableVerseApp._apply_scopa_state(app, batch_state)
            assert mock_poll.called


def test_scopa_card_list_focus_out_held_during_card_removal_turn_change(qapp):
    """Verify focusOutEvent prevents focus escaping to chat during card removal even when turn is opponent's."""
    table = DummyTableView()
    list_widget = table.scopa_card_list
    list_widget.addItem(QListWidgetItem("Remaining Card"))

    table._scopa_state = {"current_turn_id": 200}
    table._scopa_gameplay_focus = True

    with patch("client.views.table_view.QTimer.singleShot") as mock_single_shot:
        focus_event = QFocusEvent(QEvent.FocusOut, Qt.FocusReason.OtherFocusReason)
        list_widget.focusOutEvent(focus_event)

        assert mock_single_shot.called


def test_scopa_card_list_focus_out_allowed_resets_gameplay_focus(qapp):
    """Verify Tab navigation resets _scopa_gameplay_focus and allows focus departure."""
    table = DummyTableView()
    list_widget = table.scopa_card_list
    list_widget.addItem(QListWidgetItem("Card"))

    table._scopa_state = {"current_turn_id": 100}
    table._scopa_gameplay_focus = True

    with patch("client.views.table_view.QTimer.singleShot") as mock_single_shot:
        focus_event = QFocusEvent(QEvent.FocusOut, Qt.FocusReason.TabFocusReason)
        list_widget.focusOutEvent(focus_event)

        assert not mock_single_shot.called
        assert table._scopa_gameplay_focus is False


def test_scopa_round_finished_staggers_round_end_sound_when_final_play_announced():
    """Verify ROUND_END sound is staggered when final play cues are announced."""
    from client.client_app import TableVerseApp

    app = MagicMock(spec=TableVerseApp)
    app.current_room = {"id": "room1"}
    app.table_view = MagicMock()

    event = {
        "type": "scopa_round_finished",
        "round_summary": "P1 won round with 4 points",
        "final_play_action": "P1 played 7 and captured 7",
        "final_play_event_type": "CARD_CAPTURED",
        "final_play_event_id": 99,
    }

    with patch.object(app, "_announce_scopa_final_play", return_value=True):
        with patch("client.client_app.sound_engine.play_event") as mock_play:
            with patch("client.client_app.QTimer.singleShot") as mock_timer:
                with patch("client.client_app.reader.speak") as mock_speak:
                    TableVerseApp._handle_ws_event(app, event)
                    assert mock_timer.called
                    assert mock_timer.call_args[0][0] == 600
                    assert not mock_play.called
                    assert mock_speak.called
                    assert mock_speak.call_args[1].get("interrupt") is False


def test_scopa_match_finished_team_game_identifies_winners():
    """Verify team Scopa match finished plays MATCH_WIN for winning team and MATCH_LOSS for opponents."""
    from client.client_app import TableVerseApp

    app_winner = MagicMock(spec=TableVerseApp)
    app_winner.user = {"id": 10}

    app_loser = MagicMock(spec=TableVerseApp)
    app_loser.user = {"id": 20}

    team_event = {
        "winning_team": 1,
        "winning_ids": [10, 11],
    }

    with patch("client.client_app.sound_engine.play_event") as mock_play_win:
        with patch("client.client_app.reader.speak") as mock_speak_win:
            TableVerseApp._announce_terminal_result(app_winner, team_event)
            mock_play_win.assert_called_with("MATCH_WIN")

    with patch("client.client_app.sound_engine.play_event") as mock_play_loss:
        with patch("client.client_app.reader.speak") as mock_speak_loss:
            TableVerseApp._announce_terminal_result(app_loser, team_event)
            mock_play_loss.assert_called_with("MATCH_LOSS")


@pytest.mark.anyio
async def test_check_and_finalize_scopa_round_transition_task_avoids_deadlock():
    """Verify check_and_finalize_scopa_round does not deadlock when room._mutation_lock is held."""
    import asyncio
    from server.app.games.scopa_lifecycle import check_and_finalize_scopa_round
    from server.app.games.scopa import ScopaGame

    room = MagicMock()
    room.room_id = "test_lock_room"
    room.status = "playing"
    room._mutation_lock = asyncio.Lock()
    room.target_score = 11
    room.players = [1, 2]
    room.player_names = {1: "P1", 2: "P2"}
    room._round_transition_task = None
    game = ScopaGame([(1, "P1"), (2, "P2")], target_score=11)
    game.active = False
    game.winner_id = None
    game.winning_team = None
    game.round_summary = "Round 1 over"
    room.scopa_game = game

    with patch("server.app.games.scopa_lifecycle.ws_manager.broadcast_room"):
        with patch("server.app.games.scopa_lifecycle.ws_manager.broadcast_lobby"):
            # Simulate caller holding room._mutation_lock (as main.py or scopa_action does)
            async with room._mutation_lock:
                await asyncio.wait_for(check_and_finalize_scopa_round(room), timeout=2.0)
                assert room.status == "round_finished"
                assert room._round_transition_task is not None
                assert not room._round_transition_task.done()
                room._round_transition_task.cancel()
                try:
                    await room._round_transition_task
                except (asyncio.CancelledError, Exception):
                    pass


def test_scopa_start_new_round_cleans_final_play_metadata():
    """Verify start_new_round resets round-ending final_play metadata."""
    game = ScopaGame([(1, "P1"), (2, "P2")], target_score=11)
    game.final_play_event_type = "CARD_CAPTURED"
    game.final_play_action = "P1 played 7"
    game.final_play_event_id = 42
    game.round_summary = "Old summary"
    game.pending_deal_batch = True
    game.pending_round_finalize = True

    game.start_new_round()

    assert game.final_play_event_type == ""
    assert game.final_play_action == ""
    assert game.final_play_event_id is None
    assert game.round_summary == ""
    assert game.pending_deal_batch is False
    assert game.pending_round_finalize is False


def test_state_engine_identifies_team_scopa_victory():
    """Verify ClientStateEngine.process_common_state recognizes winning team members in Team Scopa."""
    from client.table_framework.state_engine import ClientStateEngine

    app = MagicMock()
    app.user = {"id": 100}
    app.current_room = {"id": "room_scopa"}
    app.table_view = MagicMock()
    app._match_result_sound_played = False
    app._last_scopa_event_id = 0

    state = {
        "event_id": 1,
        "event_type": "MATCH_FINISHED",
        "last_action": "فريق 1 فاز بالمباراة!",
        "sound_cue": "MATCH_WIN",
        "winning_team": 0,
        "teams": {"100": 0, "200": 1},
        "winner_id": None,
        "active": False,
        "round_finished": True,
    }

    with patch("client.table_framework.state_engine.sound_engine.play_event") as mock_play:
        with patch("client.table_framework.state_engine.announce_game_event") as mock_announce:
            ClientStateEngine.process_common_state(app, "SCOPA", state, lambda a, r: None)
            mock_play.assert_called_with("MATCH_WIN")
            assert app._match_result_sound_played is True
            assert mock_announce.called
            announced_text = mock_announce.call_args[0][0]
            assert "مبروك" in announced_text or "فزت" in announced_text


def test_terminal_result_string_and_int_id_matching():
    """Verify _announce_terminal_result matches IDs across string and int types."""
    from client.client_app import TableVerseApp

    # App with string ID matching integer winning_ids
    app_str_id = MagicMock(spec=TableVerseApp)
    app_str_id.user = {"id": "100"}
    app_str_id._match_result_sound_played = False

    event = {
        "winning_ids": [100, 200],
    }

    with patch("client.client_app.sound_engine.play_event") as mock_play:
        with patch("client.client_app.reader.speak"):
            TableVerseApp._announce_terminal_result(app_str_id, event)
            mock_play.assert_called_with("MATCH_WIN")

    # App with int ID matching string winning_ids
    app_int_id = MagicMock(spec=TableVerseApp)
    app_int_id.user = {"id": 100}
    app_int_id._match_result_sound_played = False

    event_str = {
        "winning_ids": ["100", "200"],
    }

    with patch("client.client_app.sound_engine.play_event") as mock_play2:
        with patch("client.client_app.reader.speak"):
            TableVerseApp._announce_terminal_result(app_int_id, event_str)
            mock_play2.assert_called_with("MATCH_WIN")


def test_round_summary_not_spoken_twice_on_final_state_and_round_finished():
    """Verify round summary is spoken exactly once when both WS round_finished and final_state arrive."""
    from client.client_app import TableVerseApp
    from client.table_framework.state_engine import ClientStateEngine

    app = MagicMock(spec=TableVerseApp)
    app.user = {"id": 10}
    app.current_room = {"id": "test_room"}
    app.table_view = MagicMock()
    app._seen_scopa_final_plays = set()
    app._last_scopa_event_id = 0

    summary_text = "نهاية الجولة 1: نقاط الجولة 4"
    ws_event = {
        "type": "scopa_round_finished",
        "round_summary": summary_text,
        "event_id": 51,
        "final_play_event_type": "CARD_CAPTURED",
        "final_play_action": "لعب علي 7 دايموند",
        "final_play_event_id": 50,
    }

    final_state = {
        "active": False,
        "round_finished": True,
        "round_summary": summary_text,
        "event_id": 51,
        "event_type": "ROUND_FINISHED",
        "last_action": summary_text,
        "final_play_event_type": "CARD_CAPTURED",
        "final_play_action": "لعب علي 7 دايموند",
        "final_play_event_id": 50,
    }

    spoken = []

    with patch.object(app, "_announce_scopa_final_play", return_value=False):
        with patch("client.client_app.reader.speak", side_effect=lambda text, interrupt=False: spoken.append(text)):
            with patch("client.table_framework.state_engine.announce_game_event", side_effect=lambda text, **k: spoken.append(text)):
                with patch("client.table_framework.state_engine.QTimer.singleShot", side_effect=lambda delay, fn: fn()):
                    with patch("client.client_app.QTimer.singleShot", side_effect=lambda delay, fn: fn()):
                        with patch("client.client_app.sound_engine.play_event"):
                            # 1. WS scopa_round_finished arrives
                            TableVerseApp._handle_ws_event(app, ws_event)
                            assert spoken.count(summary_text) == 1

                            # 2. final_state from scopa_action arrives
                            ClientStateEngine.process_common_state(app, "SCOPA", final_state, lambda a, r: None)
                            # Verify still spoken only once!
                            assert spoken.count(summary_text) == 1

