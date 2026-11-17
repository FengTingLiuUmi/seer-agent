"""雷小伊脱机日常 2.0.9 的协议/脚本/战斗/观测重建。"""

__version__ = "0.1.0"

from .protocol import Frame, FrameSplitter, H5Encoder, FlashEncoder, pack_h5, pack_flash, parse_h5, parse_flash
from .login import LoginSession, authenticate, oauth_authorize_url, exchange_code, get_gateway, parse_gateway
from .client import GameClient
from .battle import Battle, simulate
from .battle_data import BattleData
from .cjc import BattlePlan, PetPlan
from .daily import DailyRunner, TaskContext, builtin_tasks, load_app_daily_config
from .progress import ProgressTracker, Observer
from .applog import parse_daily_log, summarize, parse_battle_record
from .captures import iter_capture, summarize as summarize_capture
from .provider import SeerApiProvider, SeerApiError, build_provider
from .features import FeatureStep, bag_steps, factor_steps
from .session import GameSession, LoginInfo

__all__ = [
    "Frame", "FrameSplitter", "H5Encoder", "FlashEncoder", "pack_h5", "pack_flash", "parse_h5", "parse_flash",
    "LoginSession", "authenticate", "oauth_authorize_url", "exchange_code", "get_gateway", "parse_gateway",
    "GameClient", "Battle", "simulate", "BattleData", "BattlePlan", "PetPlan",
    "DailyRunner", "TaskContext", "builtin_tasks", "load_app_daily_config",
    "ProgressTracker", "Observer",
]