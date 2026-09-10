"""
Real Tennis Table Game Engine (Built upon leap_tennis_win by SciFY & nzorb).

=== ARCHITECTURE & TIMESTAMPS ===
State Machine:
    0  → INIT: Game initialization
    1  → WAITING_KEY: Waiting for player serve
    2  → IN_PLAY: Active point rally
    16 → GAME_OVER: Match concluded

=== BALL TIMELINE (Active Runtime Execution) ===
    launch_time (0.00 * T)  → Strike (hit_1 / hit_2)
         │
         ├──[0.50 * T]── net_time    → Net crossing whoosh (air_*.wav)
         │
         ├──[0.75 * T]── floor_time  → Floor bounce on receiving side (bounce_*.wav)
         │
         └──[1.00 * T]── reach_time  → Baseline reach (Racket hit OR point lost)

=== AUDIO PERSPECTIVE (3-Lane Discrete Stereo Panning) ===
    - Lane -1 (Left):   Left channel pan (95% Left)
    - Lane  0 (Center): Balanced center pan (50/50)
    - Lane +1 (Right):  Right channel pan (95% Right)

=== SCORING (Standard ATP/ITF Tennis Rules) ===
    Points: 0 -> 15 -> 30 -> 40 -> Deuce / Advantage -> Game
    Sets: 6 Games with a 2-game margin (Best of 3 Sets for match win)
    Server: Alternates after every finished game

=== BOT EXECUTION ===
    Autonomous opponent logic runs natively inside server tick(20ms)
    with human-like reaction probabilities and cross-court fatigue.
"""

import time
import random
from enum import IntEnum
from typing import Optional, Dict, List

# Ball lane codes (TennisGameState.target)
LANE_LEFT   = -1
LANE_CENTER =  0
LANE_RIGHT  =  1
ALL_LANES   = [LANE_LEFT, LANE_CENTER, LANE_RIGHT]


class Timestamp(IntEnum):
    """State machine timestamps from TennisGameEngineInitiator.cs"""
    INIT        = 0   # initialization — play new_game_intro
    WAITING_KEY = 1   # waiting for any keypress to launch ball
    IN_PLAY     = 2   # normal gameplay
    GAME_OVER_A = 16  # game over (level > 1)
    GAME_OVER_B = 18  # game over (level == 1)


class BallState:
    """Complete ball position and timing state matching original Leap Tennis physics."""
    def __init__(self):
        self.target:      int   = LANE_CENTER  # destination lane
        self.direction:   int   = 1            # 1=toward player, -1=toward wall
        self.launch_time: float = 0.0
        self.travel_time: float = 0.0
        self.net_time:    float = 0.0          # when net_pass fires (50% midpoint)
        self.floor_time:  float = 0.0          # when floor_hit fires (75% on receiving court)
        self.reach_time:  float = 0.0          # when ball arrives (100% baseline)

        self.net_fired:   bool  = False
        self.floor_fired: bool  = False
        self.reached:     bool  = False

    def launch(self, target: int, direction: int, travel_time: float):
        """
        Exact Leap Tennis physics timeline:
          - 0.00 * T: Strike (hit_1 or hit_2)
          - 0.50 * T: Net crossing whoosh (air.wav)
          - 0.75 * T: Floor bounce on receiving side (bounce.wav)
          - 1.00 * T: Baseline reach (racket hit or miss)
        """
        self.target      = target
        self.direction   = direction
        self.launch_time = time.monotonic()
        self.travel_time = travel_time
        self.net_time    = self.launch_time + (self.travel_time * 0.50)
        self.floor_time  = self.launch_time + (self.travel_time * 0.75)
        self.reach_time  = self.launch_time + self.travel_time
        self.net_fired   = False
        self.floor_fired = False
        self.reached     = False

    def as_dict(self) -> Dict:
        return {
            "target":      self.target,
            "direction":   self.direction,
            "launch_time": self.launch_time,
            "travel_time": self.travel_time,
            "net_time":    self.net_time,
            "floor_time":  self.floor_time,
            "reach_time":  self.reach_time,
        }


class RealTennisScore:
    """Standard International Tennis Scoring (ATP/WTA Rules)."""
    POINTS = [0, 15, 30, 40]

    def __init__(self):
        self.points = {0: 0, 1: 0}   # 0=0, 1=15, 2=30, 3=40, 4=AD
        self.games = {0: 0, 1: 0}
        self.sets = {0: 0, 1: 0}
        self.server_idx = 0          # 0=Player, 1=Opponent
        self.tiebreak_points = {0: 0, 1: 0}
        self.in_tiebreak = False
        self.tiebreak_server_start = 0
        
    def add_point(self, winner_idx: int) -> Dict:
        """Add a point using standard tennis scoring, including a 6-6 tiebreak."""
        if winner_idx not in (0, 1):
            raise ValueError("Invalid tennis player index")

        if self.in_tiebreak:
            self.tiebreak_points[winner_idx] += 1
            total = self.tiebreak_points[0] + self.tiebreak_points[1]
            # First tiebreak point is served by the set's next server; then the
            # serve changes every two points.
            if total == 1:
                self.server_idx = 1 - self.tiebreak_server_start
            elif total > 1 and total % 2 == 1:
                self.server_idx = 1 - self.server_idx
            events = ["point_won", "tiebreak_point"]
            a, b = self.tiebreak_points[0], self.tiebreak_points[1]
            if (a >= 7 or b >= 7) and abs(a - b) >= 2:
                winner = 0 if a > b else 1
                self.sets[winner] += 1
                self.games = {0: 0, 1: 0}
                self.tiebreak_points = {0: 0, 1: 0}
                self.in_tiebreak = False
                # The player who received the first tiebreak point serves first
                # in the new set.
                self.server_idx = 1 - self.tiebreak_server_start
                events.extend(["tiebreak_won", "set_won"])
            return {"events": events, "score": self.snapshot()}

        loser_idx = 1 - winner_idx
        events = ["point_won"]
        p_win = self.points[winner_idx]
        p_lose = self.points[loser_idx]
        game_won = False

        if p_win < 3:
            self.points[winner_idx] += 1
        elif p_win == 3:
            if p_lose < 3:
                game_won = True
            elif p_lose == 3:
                self.points[winner_idx] = 4
            elif p_lose == 4:
                self.points[loser_idx] = 3
        elif p_win == 4:
            game_won = True

        if game_won:
            set_won = self._win_game(winner_idx)
            events.append("game_won")
            if set_won:
                events.append("set_won")
        return {"events": events, "score": self.snapshot()}

    def _win_game(self, winner_idx: int) -> bool:
        self.games[winner_idx] += 1
        self.points = {0: 0, 1: 0}
        gw = self.games[winner_idx]
        gl = self.games[1 - winner_idx]
        set_won = False
        if gw == 6 and gl == 6:
            self.in_tiebreak = True
            self.tiebreak_points = {0: 0, 1: 0}
            self.tiebreak_server_start = self.server_idx
            return False
        if gw >= 6 and (gw - gl) >= 2:
            self.sets[winner_idx] += 1
            self.games = {0: 0, 1: 0}
            set_won = True
        self.server_idx = 1 - self.server_idx
        return set_won

    def snapshot(self) -> Dict:
        def pt_str(p):
            return str(self.POINTS[p]) if p < 4 else "AD"
            
        return {
            "points": {0: pt_str(self.points[0]), 1: pt_str(self.points[1])},
            "games": {0: self.games[0], 1: self.games[1]},
            "sets": {0: self.sets[0], 1: self.sets[1]},
            "server_idx": self.server_idx,
            "tiebreak": self.in_tiebreak,
            "tiebreak_points": dict(self.tiebreak_points),
        }


class TennisGame:
    """
    Exact Python port of scify/LeapGame-tennis mechanics but with Real ATP Rules.

    Public API:
        start_game(players)            → initial state dict
        handle_action(pid, action, data) → result dict
        tick(now)                      → list of events to broadcast (called every 20ms)
    """
    BASE_TRAVEL_TIME = 1.65  # Acoustically balanced full-court travel duration

    def __init__(self, room):
        self.room        = room
        self.players:    List[Dict] = []
        self.score       = RealTennisScore()
        self.timestamp   = Timestamp.INIT
        self.ball        = BallState()
        self.player_pos  = {0: LANE_CENTER, 1: LANE_CENTER}
        self.rally_hits  = 0          # Accelerates speed with each hit in the current rally

    def current_travel_time(self) -> float:
        """
        Computes dynamic travel time that continuously speeds up with every hit:
        - Each rally hit increases speed by 4%
        """
        speed_mult = 1.0 + (self.rally_hits * 0.04)
        return max(0.85, self.BASE_TRAVEL_TIME / speed_mult)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def start_game(self, players: List[Dict]) -> Dict:
        """Initialize game — timestamp=WAITING_KEY."""
        self.players    = players
        self.score      = RealTennisScore()
        self.player_pos = {0: LANE_CENTER, 1: LANE_CENTER}
        self.rally_hits = 0
        self.timestamp  = Timestamp.WAITING_KEY
        return self.full_state()

    def handle_action(self, player_id: str, action: str, data: Dict) -> Dict:
        """
        Player actions:
            'position' → data: {lane: -1|0|1}  (continuous, every 30ms)
            'serve'    → any key → launch ball  (only in WAITING_KEY state)
        """
        idx = self._player_idx(player_id)

        if action == "position":
            lane = max(LANE_LEFT, min(LANE_RIGHT, int(data.get("lane", 0))))
            self.player_pos[idx] = lane
            return {"type": "position_ack", "lane": lane}

        if action == "serve" and self.timestamp == Timestamp.WAITING_KEY:
            if idx != self.score.server_idx:
                return {"error": "not_your_serve"}
            now = time.monotonic()
            if now < getattr(self, "serve_ready_time", 0):
                return {"error": "waiting_for_applause"}
            lane = max(LANE_LEFT, min(LANE_RIGHT, int(data.get("lane", LANE_CENTER))))
            self.player_pos[idx] = lane
            self.rally_hits = 0
            self.timestamp = Timestamp.IN_PLAY
            
            if self.score.server_idx == 0:
                result = self._launch_toward_wall()
                result.update({"sender": 0, "hit_type": "racket", "sound": "player_racket_hit", "player_idx": 0})
            else:
                result = self._launch_toward_player()
                result.update({"sender": 1, "hit_type": "racket", "sound": "opponent_racket_hit", "player_idx": 1})
                
            return result

        return {"error": "invalid_action"}

    def tick(self, now: float) -> List[Dict]:
        """
        Called every ~20ms by run_tennis_loop.
        Timeline:
          - 50%: net_pass (air.wav)
          - 75%: floor_hit (bounce.wav)
          - 100%: reach baseline (racket or wall hit)
        """
        if self.timestamp == Timestamp.WAITING_KEY:
            is_bot = (len(self.players) < 2) or (int(self.players[1].get("id", 0)) < 0)
            if is_bot and self.score.server_idx == 1:
                # Wait for crowd applause to complete (4.5s rest) before bot serves
                if not hasattr(self, "_bot_serve_time") or self._bot_serve_time is None:
                    self._bot_serve_time = max(now + 4.5, getattr(self, "serve_ready_time", now + 4.5))
                elif now >= self._bot_serve_time:
                    self._bot_serve_time = None
                    self.timestamp = Timestamp.IN_PLAY
                    self.rally_hits = 0
                    target = random.choice(ALL_LANES)
                    traj = self._launch_toward_player(target=target)
                    traj.update({
                        "hit_type":   "racket",
                        "sound":      "opponent_racket_hit",
                        "player_idx": 1,
                        "state":      self.full_state(),
                    })
                    return [traj]
            else:
                self._bot_serve_time = None
            return []

        self._bot_serve_time = None

        if self.timestamp not in (Timestamp.IN_PLAY,):
            return []

        events = []
        ball   = self.ball

        # ---- 1. Net pass at midpoint (50%) ----
        if not ball.net_fired and now >= ball.net_time:
            ball.net_fired = True
            events.append({
                "type":      "tennis_sound",
                "sound":     "net_pass",
                "lane":      ball.target,
                "direction": ball.direction,
            })

        # ---- 2. Floor hit at 75% on receiving court ----
        if not ball.floor_fired and now >= ball.floor_time:
            ball.floor_fired = True
            events.append({
                "type":      "tennis_sound",
                "sound":     "floor_hit",
                "lane":      ball.target,
                "direction": ball.direction,
            })

        # ---- 3. Ball reached destination (100%) ----
        if not ball.reached and now >= ball.reach_time:
            ball.reached        = True

            if ball.direction == 1:
                # Ball arrived at PLAYER baseline
                events += self._handle_player_reach()
            else:
                # Ball arrived at BOT/OPPONENT baseline
                events += self._handle_wall_reach()

        return events

    # ------------------------------------------------------------------
    # Collision handlers
    # ------------------------------------------------------------------

    def _handle_player_reach(self) -> List[Dict]:
        """
        Ball arrived at Player 0 baseline (direction == 1).
        "bounce" "racket" OR "bounce" "boundary"
        """
        player_lane = self.player_pos.get(0, LANE_CENTER)
        ball_lane   = self.ball.target

        if player_lane == ball_lane:
            # ===== Player 0 successfully hits ball → shoots to random lane on opponent side =====
            self.rally_hits += 1
            
            # Shoot ball to a random target lane on opponent's court (left, center, or right)
            target_lane = random.choice(ALL_LANES)
            traj = self._launch_toward_wall(target=target_lane)
            traj.update({
                "hit_type":     "racket",
                "sound":        "player_racket_hit",
                "player_idx":   0,
            })
            return [traj]
        else:
            # ===== Player 0 missed ball =====
            self.rally_hits = 0
            
            # Player 1 wins the point
            result = self.score.add_point(winner_idx=1)
            target_sets = int(getattr(self.room, "target_score", 1) or 1)
            if self.score.sets[1] >= target_sets:
                self.timestamp = Timestamp.GAME_OVER_A
                self.winner_idx = 1
                result["events"].append("match_won")
            else:
                self.timestamp = Timestamp.WAITING_KEY
                self.serve_ready_time = time.monotonic() + 4.5
                self._bot_serve_time = time.monotonic() + 4.8
            
            return [{
                "type":         "tennis_action_result",
                "hit_type":     "boundary",
                "sound":        "new_game_miss",
                "player_idx":   0,
                "score_result": result,
                "miss":         True,
                "player_lane":  player_lane,
                "ball_lane":    ball_lane,
                "state":        self.full_state(),
            }]

    def _bot_should_hit(self) -> bool:
        """
        Determines whether the bot successfully returns the ball or makes an unforced error/miss.
        Accounts for bot difficulty setting, rally speed/hits, and cross-court movement.
        """
        rules = getattr(self.room, "rules", {}) or {}
        difficulty = str(rules.get("bot_difficulty", "NORMAL")).upper()

        # Base success rate per difficulty
        base_hit_rates = {
            "EASY": 0.65,     # 35% miss rate on easy
            "NORMAL": 0.80,   # 20% miss rate on normal
            "HARD": 0.90,     # 10% miss rate on hard
            "EXPERT": 0.96,   # 4% miss rate on expert
        }
        hit_rate = base_hit_rates.get(difficulty, 0.80)

        # Longer rallies add fatigue/pressure and increase unforced errors
        if self.rally_hits > 2:
            decay = (self.rally_hits - 2) * 0.035
            hit_rate = max(0.25, hit_rate - decay)

        # Cross-court penalty: if the ball came from opposite lane (e.g. -1 to 1)
        ball_lane = self.ball.target
        prev_bot_lane = self.player_pos.get(1, LANE_CENTER)
        if abs(ball_lane - prev_bot_lane) == 2:
            hit_rate -= 0.08

        return random.random() < hit_rate

    def _handle_wall_reach(self) -> List[Dict]:
        """
        Ball arrived at Player 1 / Bot / Wall baseline (direction == -1).
        Supports Human vs Bot and Human vs Human.
        """
        is_bot = (len(self.players) < 2) or (int(self.players[1].get("id", 0)) < 0)

        if is_bot:
            ball_lane = self.ball.target
            bot_hits = self._bot_should_hit()

            if bot_hits:
                # Bot moves to the ball's lane and successfully returns it!
                self.player_pos[1] = ball_lane
                self.rally_hits += 1
                new_target = random.choice(ALL_LANES)
                traj = self._launch_toward_player(target=new_target)
                traj.update({
                    "hit_type":   "racket",
                    "sound":      "opponent_racket_hit",
                    "player_idx": 1,
                })
                return [traj]
            else:
                # Bot missed! Player 0 scores!
                self.rally_hits = 0
                
                # Pick a wrong lane to reflect bot being out of position
                wrong_lanes = [l for l in ALL_LANES if l != ball_lane]
                bot_miss_lane = random.choice(wrong_lanes) if wrong_lanes else LANE_CENTER
                self.player_pos[1] = bot_miss_lane
                
                # Player 0 wins the point
                result = self.score.add_point(winner_idx=0)
                target_sets = int(getattr(self.room, "target_score", 1) or 1)
                if self.score.sets[0] >= target_sets:
                    self.timestamp = Timestamp.GAME_OVER_A
                    self.winner_idx = 0
                    result["events"].append("match_won")
                else:
                    self.timestamp = Timestamp.WAITING_KEY
                    self.serve_ready_time = time.monotonic() + 4.5
                    self._bot_serve_time = time.monotonic() + 4.8
                
                return [{
                    "type":         "tennis_action_result",
                    "hit_type":     "boundary",
                    "sound":        "new_game_miss",
                    "player_idx":   1,
                    "score_result": result,
                    "miss":         True,
                    "player_lane":  bot_miss_lane,
                    "ball_lane":    ball_lane,
                    "state":        self.full_state(),
                }]
        else:
            # Real Human Player 1: check if Player 1 is in the correct lane!
            p1_lane = self.player_pos.get(1, LANE_CENTER)
            ball_lane = self.ball.target

            if p1_lane == ball_lane:
                # Player 1 hits the ball back to a random lane on Player 0's court!
                self.rally_hits += 1
                new_target = random.choice(ALL_LANES)
                traj = self._launch_toward_player(target=new_target)
                traj.update({
                    "hit_type":   "racket",
                    "sound":      "opponent_racket_hit",
                    "player_idx": 1,
                })
                return [traj]
            else:
                # Player 1 missed! Player 0 scores!
                self.rally_hits = 0
                
                # Player 0 wins the point
                result = self.score.add_point(winner_idx=0)
                target_sets = int(getattr(self.room, "target_score", 1) or 1)
                if self.score.sets[0] >= target_sets:
                    self.timestamp = Timestamp.GAME_OVER_A
                    self.winner_idx = 0
                    result["events"].append("match_won")
                else:
                    self.timestamp = Timestamp.WAITING_KEY
                    self.serve_ready_time = time.monotonic() + 4.5
                
                return [{
                    "type":         "tennis_action_result",
                    "hit_type":     "boundary",
                    "sound":        "new_game_miss",
                    "player_idx":   1,
                    "score_result": result,
                    "miss":         True,
                    "player_lane":  p1_lane,
                    "ball_lane":    ball_lane,
                    "state":        self.full_state(),
                }]

    # ------------------------------------------------------------------
    # Ball launching helpers
    # ------------------------------------------------------------------

    def _launch_toward_player(self, target: int = None) -> Dict:
        """Ball from opponent → player. direction=+1."""
        if target is None:
            target = random.choice(ALL_LANES)
        t_time = self.current_travel_time()
        self.ball.launch(target=target, direction=1, travel_time=t_time)
        return {
            "type":        "tennis_action_result",
            "ball":        self.ball.as_dict(),
            "travel_time": self.ball.travel_time,
            "sender":      1,   # 1 = from opponent/wall
        }

    def _launch_toward_wall(self, target: int = None) -> Dict:
        """Ball from player → opponent. direction=-1."""
        if target is None:
            target = random.choice(ALL_LANES)
        t_time = self.current_travel_time()
        self.ball.launch(target=target, direction=-1, travel_time=t_time)
        return {
            "type":        "tennis_action_result",
            "ball":        self.ball.as_dict(),
            "travel_time": self.ball.travel_time,
            "sender":      0,   # 0 = from player
        }

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _player_idx(self, player_id: str) -> int:
        for i, p in enumerate(self.players):
            if str(p.get("id")) == str(player_id):
                return i
        raise ValueError("Player not found in game")

    @property
    def state(self) -> str:
        """Legacy compat property — maps timestamp to string state."""
        if self.timestamp == Timestamp.WAITING_KEY:
            return "SERVING"
        if self.timestamp == Timestamp.IN_PLAY:
            return "IN_PLAY"
        if self.timestamp in (Timestamp.GAME_OVER_A, Timestamp.GAME_OVER_B):
            return "FINISHED"
        return "WAITING"

    @state.setter
    def state(self, value: str):
        if value == "FINISHED":
            self.timestamp = Timestamp.GAME_OVER_A
        elif value == "SERVING":
            self.timestamp = Timestamp.WAITING_KEY
        elif value == "IN_PLAY":
            self.timestamp = Timestamp.IN_PLAY

    def full_state(self) -> Dict:
        return {
            "state":            self.state,
            "timestamp":        int(self.timestamp),
            "score":            self.score.snapshot(),
            "travel_time":      self.current_travel_time(),
            "ball":             self.ball.as_dict(),
            "player_positions": dict(self.player_pos),
            "players":          self.players,
        }
