# versusai-sc2-bot-template

A template for creating StarCraft 2 AI bots using the [python-sc2](https://github.com/BurnySc2/python-sc2) framework. Includes a basic bot setup with a clean configuration system and built-in validation for workshop milestones.

🚀 **New to StarCraft 2 AI?** Check out the [Zerg Rush Bot Workshop](https://subscribe.versusai.net/zerg-rush) for a guided step-by-step build, or jump straight in with the template below.

## Features

- Simple configuration via `config.py`
- Easy setup for local development
- Support for custom maps and AI opponents
- Ready-to-use bot structure
- Built-in milestone validation (`--validate`)
- Upgradable to Ares framework

## Quick Start

### Prerequisites

- [Python](https://www.python.org/downloads/) 3.8 or newer
- [Git](https://git-scm.com/downloads)
- [StarCraft II](https://battle.net/account/download/)

### StarCraft II Installation

- **Windows**: Install through the Battle.net app
- **Linux**: 
  - Option 1: Use the [Blizzard SC2 Linux package](https://github.com/Blizzard/s2client-proto#linux-packages)
  - Option 2: Set up Battle.net via WINE using [Lutris](https://lutris.net/games/battlenet/)

### Required Maps

Download the StarCraft 2 AI Maps from [here](https://www.dropbox.com/scl/fi/sha2hnrce4wihhu62l1ty/Maps.zip?rlkey=b74sn8ee54vi1wn24sw9m9bd8&dl=1). Unzip and place the maps in the `Maps` folder in your StarCraft II installation directory. If one doesn't exist, create it.

By default, the bot will look for maps in the standard installation location. If your maps are elsewhere, update `MAP_PATH` in `config.py`.

### Linux (Lutris) Setup

If you're using Lutris on Linux, set these environment variables (replace with your actual paths):

```bash
export SC2PF=WineLinux
export SC2PATH="/home/YOUR_USERNAME/Games/battlenet/drive_c/Program Files (x86)/StarCraft II/"
export WINE="/home/YOUR_USERNAME/.local/share/lutris/runners/wine/YOUR_WINE_VERSION/bin/wine"
```

## Getting Started

1. **Create your repository** — Click the `Use this template` button above to create your own copy
2. **Clone your repository**
   ```bash
   git clone <your-repository-url>
   cd <repository-name>
   ```
3. **Set up a virtual environment**
   ```bash
   # Windows
   python -m venv venv
   .\venv\Scripts\activate

   # Linux/Mac
   python3 -m venv venv
   source venv/bin/activate
   ```
4. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```
5. **Run the bot**
   ```bash
   python run.py
   ```

## Configuration

Edit `config.py` to customize:
- **Bot name and race** (defaults to Zerg for the Zerg Rush workshop)
- **Map pool** (defaults to workshop maps: Persephone, Pylon, Torches)
- **Opponent difficulty and race**
- **Game mode** (realtime or faster simulation)

## Validating Your Progress

The template includes a built-in validator that checks your bot against Zerg Rush milestones:

```bash
python run.py --validate
```

This prints a report at game end showing which steps you've completed across 4 stages:

1. **Economy Foundation** — 16 workers, extractor, no supply blocks
2. **The Rush Core** — Spawning Pool at supply 11–14, Zerglings after pool
3. **The Speed Advantage** — Queen, Metabolic Boost after pool
4. **Attack** — Zerglings sent to enemy base

The validator is tuned for the Zerg Rush build. For step-by-step instructions that walk you through each milestone, see the [Zerg Rush Bot Workshop](https://subscribe.versusai.net/zerg-rush).

## Customizing Your Bot

### Basic Configuration
Edit `config.py` to change bot name, race, map pool, opponent, and game mode.

### Adding Logic
Modify `bot/bot.py` to implement your bot's behavior. The `on_step` method is where most of your logic goes.

### Adding New Code
As you add features, keep all new code files in the `bot/` folder — it's included when creating the ladder zip.

## Upgrading to Ares Framework

Ares-sc2 extends python-sc2 with advanced tools for more sophisticated bot behavior. To migrate your bot:

```bash
python upgrade_to_ares.py
```

The main change is that your bot inherits from `AresBot` instead of `BotAI`, and you add `super()` calls to any hook methods you use. For the full migration guide, see [Migrating to Ares](https://aressc2.github.io/ares-sc2/tutorials/migrating.html).

## Competing with Your Bot

Create a ladder-ready zip:

```bash
python create_ladder_zip.py
```

Upload the resulting `publish/bot.zip` to [AI Arena](https://aiarena.net/) or any other SC2 bot ladder.

## License

This project is licensed under the terms found in the [LICENSE](LICENSE) file.