import argparse
import asyncio
import logging
import aiohttp
import os
import sc2
from sc2.main import run_game
from sc2.data import Race, Difficulty
from sc2.client import Client
from sc2.player import Bot, Computer
from sc2.protocol import ConnectionAlreadyClosed
import random

from bot import CompetitiveBot
from config import BOT_NAME, BOT_RACE, MAP_POOL, MAP_PATH, OPPONENT_RACE, OPPONENT_DIFFICULTY, REALTIME

# Validation mixin for workshop checkpoints
# Usage: python run.py --validate
from tests.zerg_rush_validator import ZergRushValidator
from sc2.data import Race, Difficulty


# Run ladder game
# This lets python-sc2 connect to a ladder game.
# Based on: https://github.com/Dentosal/python-sc2/blob/master/examples/run_external.py
def run_ladder_game(args, bot):
    if args.LadderServer == None:
        host = "127.0.0.1"
    else:
        host = args.LadderServer

    host_port = args.GamePort
    lan_port = args.StartPort

    # Port config
    ports = [lan_port + p for p in range(1, 6)]

    portconfig = sc2.portconfig.Portconfig()
    portconfig.shared = ports[0]  # Not used
    portconfig.server = [ports[1], ports[2]]
    portconfig.players = [[ports[3], ports[4]]]

    # Join ladder game
    g = join_ladder_game(host=host, port=host_port, players=[bot], realtime=args.Realtime, portconfig=portconfig)

    # Ensure replay directory exists
    if REPLAY_SAVE_PATH and not os.path.exists(REPLAY_SAVE_PATH):
        os.makedirs(REPLAY_SAVE_PATH, exist_ok=True)
    
    # Run the game
    result = asyncio.get_event_loop().run_until_complete(g)
    
    # Save replay if we have a path and a result
    if result and REPLAY_SAVE_PATH:
        replay_path = os.path.join(REPLAY_SAVE_PATH, f"{BOT_NAME}_vs_{args.OpponentId}.SC2Replay")
        try:
            result.save_replay(replay_path)
            print(f"Replay saved to: {replay_path}")
        except Exception as e:
            print(f"Failed to save replay: {e}")
    
    return result, args.OpponentId


# Modified version of sc2.main._join_game to allow custom host and port, and to not spawn an additional sc2process (thanks to alkurbatov for fix)
async def join_ladder_game(
        host, port, players, realtime, portconfig, save_replay_as=None, step_time_limit=None, game_time_limit=None
):
    ws_url = "ws://{}:{}/sc2api".format(host, port)
    ws_connection = await aiohttp.ClientSession().ws_connect(ws_url, timeout=120)
    client = Client(ws_connection)
    try:
        result = await sc2.main._play_game(players[0], client, realtime, portconfig, step_time_limit, game_time_limit)
        if save_replay_as is not None:
            await client.save_replay(save_replay_as)
        # await client.leave()
        # await client.quit()
    except ConnectionAlreadyClosed:
        logging.error(f"Connection was closed before the game ended")
        return None
    finally:
        await ws_connection.close()

    return result


def parse_arguments():
    # Load command line arguments
    parser = argparse.ArgumentParser()

    # Ladder play arguments
    parser.add_argument("--GamePort", type=int, help="Game port.")
    parser.add_argument("--StartPort", type=int, help="Start port.")
    parser.add_argument("--LadderServer", type=str, help="Ladder server.")

    # Bot settings
    parser.add_argument("--bot-name", type=str, default=BOT_NAME,
                       help=f"Name of your bot. Default: {BOT_NAME}")
    parser.add_argument("--bot-race", type=str, default=BOT_RACE,
                       help=f"Bot race (Terran, Zerg, Protoss, Random). Default: {BOT_RACE}")
    
    # Game settings
    parser.add_argument("--map", type=str, default=None,
                       help=f"Map to play on. If not specified, a random map will be selected from: {', '.join(MAP_POOL)}")
    parser.add_argument("--opponent-race", type=str, default=OPPONENT_RACE,
                       help=f"Computer race (Terran, Zerg, Protoss, Random). Default: {OPPONENT_RACE}")
    parser.add_argument("--difficulty", type=str, default=OPPONENT_DIFFICULTY,
                       help=f"Computer difficulty (VeryEasy to VeryHard). Default: {OPPONENT_DIFFICULTY}")
    parser.add_argument("--realtime", action='store_true', default=REALTIME,
                       help=f"Play in realtime. Default: {REALTIME}")
    parser.add_argument("--validate", action='store_true', default=False,
                       help="Run Zerg Rush validation during the game. Prints a milestone report at game end.")
    parser.add_argument("--sc2-version", type=str, help="Starcraft 2 game version (optional)")

    args, unknown_args = parser.parse_known_args()

    for unknown_arg in unknown_args:
        print(f"Unknown argument: {unknown_arg}")

    # Set default opponent ID if not provided
    if not hasattr(args, 'OpponentId') or not args.OpponentId:
        args.OpponentId = f"{args.opponent_race}_{args.difficulty}"

    return args


def load_bot(args):
    """Initialize and configure the bot."""
    # If --validate flag is set, dynamically mix ZergRushValidator into
    # CompetitiveBot so the validation report prints at game end.
    if args.validate:
        class ValidatedCompetitiveBot(ZergRushValidator, CompetitiveBot):
            """CompetitiveBot with ZergRushValidator mixed in at runtime."""

            async def on_step(self, iteration: int):
                await ZergRushValidator.on_step(self, iteration)
                await CompetitiveBot.on_step(self, iteration)

            async def on_start(self):
                await ZergRushValidator.on_start(self)
                await CompetitiveBot.on_start(self)

            async def on_end(self, game_result):
                await ZergRushValidator.on_end(self, game_result)
                await CompetitiveBot.on_end(self, game_result)

        bot = ValidatedCompetitiveBot()
        print("Zerg Rush validation ENABLED — report will print at game end.")
    else:
        bot = CompetitiveBot()

    # Convert string race to Race enum
    try:
        bot_race = Race[args.bot_race.capitalize()]
    except KeyError:
        print(f"Invalid bot race: {args.bot_race}. Using Terran.")
        bot_race = Race.Terran

    # Return configured bot
    return Bot(bot_race, bot)


def run():
    """Legacy run function - kept for compatibility."""
    print("Warning: Using legacy run() function. Consider updating your code.")
    main()


def main():
    """Main function to run the bot."""
    # Parse command line arguments
    args = parse_arguments()
    
    # Simple console logging
    logging.basicConfig(
        level=logging.INFO,
        format="%(message)s",
    )
    
    # Get bot name and race from args (with fallback to config)
    bot_name = getattr(args, 'bot_name', BOT_NAME)
    bot_race = getattr(args, 'bot_race', BOT_RACE)
    
    print(f"===== {bot_name} ({bot_race}) =====")
    print(f"Available maps: {', '.join(MAP_POOL)}")
    print(f"Opponent: {args.opponent_race} {args.difficulty}")
    print(f"Realtime: {'Yes' if args.realtime else 'No'}")
    
    try:
        # Load and run the bot
        bot = load_bot(args)

        # Convert string to Race and Difficulty enums for opponent
        try:
            opponent_race = Race[args.opponent_race.capitalize()]
        except KeyError:
            print(f"Invalid opponent race: {args.opponent_race}. Using Terran.")
            opponent_race = Race.Terran
        try:
            difficulty = Difficulty[args.difficulty]
        except KeyError:
            print(f"Invalid difficulty: {args.difficulty}. Using VeryHard.")
            difficulty = Difficulty.VeryHard

        # Select a random map if none specified
        map_name = args.map if args.map else random.choice(MAP_POOL)

        # Get map from specified path or default SC2 maps
        if MAP_PATH and os.path.exists(MAP_PATH):
            try:
                print(f"Loading map from custom path: {MAP_PATH}")
                # Use the map_dir parameter directly with the full Maps path
                map_obj = sc2.maps.get(map_name, map_dir=MAP_PATH)
            except Exception as e:
                print(f"Error loading custom map: {e}")
                print("Falling back to default SC2 maps...")
                map_obj = sc2.maps.get(map_name)
        else:
            map_obj = sc2.maps.get(map_name)

        # Start a local game
        print(f"\nStarting game on {map_name}...")
        run_game(
            map_obj,
            [bot, Computer(opponent_race, difficulty)],
            realtime=args.realtime,
            sc2_version=args.sc2_version if hasattr(args, 'sc2_version') else None
        )
    except KeyboardInterrupt:
        print("\nGame stopped by user")
    except Exception as e:
        print(f"\nAn error occurred: {e}")
        if __debug__:
            import traceback
            traceback.print_exc()
        return 1
    return 0

if __name__ == "__main__":
    import sys
    sys.exit(main())
