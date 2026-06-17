"""In-game Zerg Rush Step Validator — tracks milestones during a live game.

This module provides a ``ZergRushValidator`` mixin that hooks into the
python-sc2 bot lifecycle and evaluates the 4 progressive stages from
the VersusAI Workshop:

  Stage 1: Economy Foundation — 16 workers, Extractor, no supply blocks
  Stage 2: The Rush Core — Spawning Pool, Zerglings
  Stage 3: The Speed Advantage — Queen Injects, Metabolic Boost
  Stage 4: Attack — Zerglings sent to enemy base

Usage — mix into your bot BEFORE BotAI::

    from tests.zerg_rush_validator import ZergRushValidator

    class MyBot(ZergRushValidator, BotAI):
        async def on_step(self, iteration):
            await super().on_step(iteration)
            # ... your bot logic ...

When the game ends the validator prints a report like::

    ═══════════════════════════════════════════
    ZERG RUSH VALIDATION REPORT
    ═══════════════════════════════════════════
    Stage 1: Economy Foundation
      Workers to 16 .............. PASS
      Workers Before Pool ........ PASS
      Extractor Built ............ PASS
      Supply Management ........... PASS
    Stage 2: The Rush Core
      Spawning Pool Built ........ PASS
      Pool Timing ................. PASS
      Pool Supply ................. PASS
      Only One Pool ............... PASS
      Zerglings Produced ......... PASS
      Zerglings After Pool ........ PASS
    Stage 3: The Speed Advantage
      Queen Produced ............. PASS
      Zergling Speed .............. PASS
      Speed Timing ................ PASS
      Speed After Pool ............ PASS
    Stage 4: Attack
      Attack Enemy Base ........... PASS
      Attack Timing ............... PASS
      Zergling Count .............. PASS
    ═══════════════════════════════════════════
    15/16 passed  (93.8%)
    ═══════════════════════════════════════════

Criteria sourced from:
  tests/test_zerg_rush_reference.py
  https://community.versusai.net/t/creating-a-zerg-rush-bot-in-python-from-scratch/40
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional

from sc2.ids.unit_typeid import UnitTypeId
from sc2.ids.upgrade_id import UpgradeId


# ── Step result ─────────────────────────────────────────────────────────────

@dataclass
class StepResult:
    """Outcome of a single validation step."""
    name: str
    passed: bool = False
    detail: str = ""

    def __str__(self) -> str:
        status = "PASS" if self.passed else "FAIL"
        if self.detail:
            return f"{status} ({self.detail})"
        return status


# ── Validator mixin ─────────────────────────────────────────────────────────

class ZergRushValidator:
    """Mixin that validates Zerg Rush milestones during a live game.

    Mix this into your bot class BEFORE BotAI so that super() calls
    reach the framework::

        class MyBot(ZergRushValidator, BotAI):
            async def on_step(self, iteration):
                await super().on_step(iteration)  # triggers validator tracking
                # your logic here

    IMPORTANT: The validator's on_step does NOT call super().on_step()
    because BotAI.on_step raises NotImplementedError. Instead, the bot's
    own on_step calls super() which hits the validator first, then the
    bot adds its logic after.
    """

    # ── Timing thresholds (game seconds) ────────────────────────────────
    POOL_DEADLINE: float = 50.0       # Pool started by ~0:50
    SPEED_DEADLINE: float = 180.0     # Speed started by ~3:00
    ATTACK_DEADLINE: float = 270.0    # Attack by ~4:30

    # ── Supply thresholds ───────────────────────────────────────────────
    POOL_SUPPLY_MIN: float = 11
    POOL_SUPPLY_MAX: float = 14
    MIN_ZERGLING_COUNT: int = 6

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)

    def _init_validator_state(self):
        """Initialize tracking state. Called from on_start or first on_step."""
        if hasattr(self, '_validator_initialized'):
            return
        self._max_workers: int = 0
        self._workers_at_pool_start: int = 0
        self._pool_started: bool = False
        self._pool_start_time: Optional[float] = None
        self._pool_start_supply: Optional[float] = None
        self._pool_count: int = 0
        self._extractor_built: bool = False
        self._zerglings_produced: bool = False
        self._zerglings_before_pool: bool = False
        self._zergling_count: int = 0
        self._queen_produced: bool = False
        self._speed_started: bool = False
        self._speed_start_time: Optional[float] = None
        self._attack_sent: bool = False
        self._attack_time: Optional[float] = None
        self._supply_blocked_frames: int = 0
        self._total_frames: int = 0
        self._validator_initialized: bool = True

    # ── Lifecycle hooks ─────────────────────────────────────────────────

    async def on_start(self):
        """Called at game start — initialize tracking."""
        self._init_validator_state()

    async def on_step(self, iteration: int):
        """Called every frame — track milestones from live game state.

        Does NOT call super().on_step() because BotAI.on_step raises
        NotImplementedError. The bot's own on_step should call
        ``await super().on_step(iteration)`` to trigger this tracking,
        then add its own logic after.
        """
        self._init_validator_state()
        self._total_frames += 1

        # Track max workers
        worker_count = self.workers.amount
        if worker_count > self._max_workers:
            self._max_workers = worker_count

        # Track supply blocks (supply_left == 0 for extended time)
        if self.supply_left == 0 and not self._pool_started:
            self._supply_blocked_frames += 1

        # Track extractor
        if not self._extractor_built and self.gas_buildings.amount > 0:
            self._extractor_built = True

        # Track spawning pool
        if not self._pool_started:
            pool_count = self.structures(UnitTypeId.SPAWNINGPOOL).amount
            pending = self.already_pending(UnitTypeId.SPAWNINGPOOL)
            if pool_count + pending > 0:
                self._pool_started = True
                self._pool_start_time = self.time
                self._pool_start_supply = self.supply_used
                self._workers_at_pool_start = self.workers.amount
                self._pool_count = pool_count + pending

        # Track max pool count (shouldn't build more than 1)
        current_pool = self.structures(UnitTypeId.SPAWNINGPOOL).amount
        if current_pool > self._pool_count:
            self._pool_count = current_pool

        # Track zerglings
        zergling_count = self.units(UnitTypeId.ZERGLING).amount
        if zergling_count > 0:
            if not self._zerglings_produced:
                self._zerglings_produced = True
                # Check if zerglings appeared before pool started
                if not self._pool_started:
                    self._zerglings_before_pool = True
            self._zergling_count = max(self._zergling_count, zergling_count)

        # Track queen
        if not self._queen_produced and self.units(UnitTypeId.QUEEN).amount > 0:
            self._queen_produced = True

        # Track zergling speed
        if not self._speed_started:
            if self.already_pending_upgrade(UpgradeId.ZERGLINGMOVEMENTSPEED) > 0:
                self._speed_started = True
                self._speed_start_time = self.time

        # Track attack — zerglings moving away from start toward enemy
        if not self._attack_sent and self._zergling_count > 0:
            zerglings = self.units(UnitTypeId.ZERGLING)
            if zerglings:
                start_loc = self.start_location
                enemy_loc = self.enemy_start_locations[0] if self.enemy_start_locations else None
                if enemy_loc:
                    for zl in zerglings:
                        dist_to_start = zl.distance_to(start_loc)
                        dist_to_enemy = zl.distance_to(enemy_loc)
                        # Zergling is closer to enemy than to start → attacking
                        if dist_to_enemy < dist_to_start and dist_to_start > 20:
                            self._attack_sent = True
                            self._attack_time = self.time
                            break

    async def on_end(self, game_result):
        """Called at game end — print the validation report."""
        report = self.validate()
        self._print_report(report)

    # ── Validation logic ─────────────────────────────────────────────────

    def validate(self) -> Dict[str, List[StepResult]]:
        """Evaluate all milestones and return results grouped by stage."""
        self._init_validator_state()
        stages: Dict[str, List[StepResult]] = {}

        # ── Stage 1: Economy Foundation ─────────────────────────────────
        stages["Stage 1: Economy Foundation"] = [
            StepResult(
                "Workers to 16",
                self._max_workers >= 16,
                f"max workers: {self._max_workers}"
            ),
            StepResult(
                "Workers Before Pool",
                self._workers_at_pool_start >= 12,
                f"workers at pool start: {self._workers_at_pool_start}"
            ),
            StepResult(
                "Extractor Built",
                self._extractor_built,
            ),
            StepResult(
                "Supply Management",
                self._supply_blocked_frames < 50,  # less than ~2s of supply block
                f"supply-blocked frames: {self._supply_blocked_frames}"
            ),
        ]

        # ── Stage 2: The Rush Core ──────────────────────────────────────
        stages["Stage 2: The Rush Core"] = [
            StepResult(
                "Spawning Pool Built",
                self._pool_started,
            ),
            StepResult(
                "Pool Timing",
                self._pool_start_time is not None and self._pool_start_time <= self.POOL_DEADLINE,
                f"pool at {self._pool_start_time:.1f}s" if self._pool_start_time else "no pool"
            ),
            StepResult(
                "Pool Supply",
                self._pool_start_supply is not None
                and self.POOL_SUPPLY_MIN <= self._pool_start_supply <= self.POOL_SUPPLY_MAX,
                f"supply at pool start: {self._pool_start_supply}" if self._pool_start_supply else "no pool"
            ),
            StepResult(
                "Only One Pool",
                self._pool_count <= 1,
                f"pool count: {self._pool_count}"
            ),
            StepResult(
                "Zerglings Produced",
                self._zerglings_produced,
            ),
            StepResult(
                "Zerglings After Pool",
                self._zerglings_produced and not self._zerglings_before_pool,
            ),
        ]

        # ── Stage 3: The Speed Advantage ────────────────────────────────
        stages["Stage 3: The Speed Advantage"] = [
            StepResult(
                "Queen Produced",
                self._queen_produced,
            ),
            StepResult(
                "Zergling Speed",
                self._speed_started,
            ),
            StepResult(
                "Speed Timing",
                self._speed_start_time is not None and self._speed_start_time <= self.SPEED_DEADLINE,
                f"speed at {self._speed_start_time:.1f}s" if self._speed_start_time else "no speed"
            ),
            StepResult(
                "Speed After Pool",
                (self._speed_started and self._pool_started
                 and self._speed_start_time is not None
                 and self._pool_start_time is not None
                 and self._speed_start_time > self._pool_start_time),
            ),
        ]

        # ── Stage 4: Attack ──────────────────────────────────────────────
        stages["Stage 4: Attack"] = [
            StepResult(
                "Attack Enemy Base",
                self._attack_sent,
            ),
            StepResult(
                "Attack Timing",
                self._attack_time is not None and self._attack_time <= self.ATTACK_DEADLINE,
                f"attack at {self._attack_time:.1f}s" if self._attack_time else "no attack"
            ),
            StepResult(
                "Zergling Count",
                self._zergling_count >= self.MIN_ZERGLING_COUNT,
                f"max zerglings: {self._zergling_count}"
            ),
        ]

        return stages

    # ── Report formatting ───────────────────────────────────────────────

    @staticmethod
    def _print_report(stages: Dict[str, List[StepResult]]) -> None:
        """Print a human-readable validation report to stdout."""
        total_passed = 0
        total_steps = 0

        width = 50
        print()
        print("═" * width)
        print("ZERG RUSH VALIDATION REPORT")
        print("═" * width)

        for stage_name, steps in stages.items():
            print(f"\n  {stage_name}")
            for step in steps:
                total_steps += 1
                if step.passed:
                    total_passed += 1
                # Pad the step name so the status lines up
                pad = 28 - len(step.name)
                line = f"    {step.name} {'.' * max(pad, 3)} {step}"
                print(line)

        print()
        print("═" * width)
        pct = (total_passed / total_steps * 100) if total_steps else 0
        print(f"  {total_passed}/{total_steps} passed  ({pct:.1f}%)")
        print("═" * width)
        print()

    def get_score(self) -> Dict[str, int]:
        """Return a simple score dict for programmatic use."""
        stages = self.validate()
        total = 0
        passed = 0
        for steps in stages.values():
            for step in steps:
                total += 1
                if step.passed:
                    passed += 1
        return {"steps_total": total, "steps_passed": passed, "steps_failed": total - passed}