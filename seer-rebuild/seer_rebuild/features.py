"""2.0.9 精灵背包/装备 与 精灵因子 的 C2S 构造器。

数据来自 `feature1.pcapng` / `feature2.pcapng`（账号 ACCOUNT）的 C2S 帧。
这里只构造已捕获的命令，不做服务端语义猜测；`PET_RELEASE(2304)` 已捕获但
故意不提供，避免误删精灵。
"""
from __future__ import annotations

import struct
from dataclasses import dataclass, field


def u32(v: int) -> bytes:
    return struct.pack(">I", v & 0xFFFFFFFF)


def u32s(values: list[int] | tuple[int, ...]) -> bytes:
    return b"".join(u32(v) for v in values)


def list_body(values: list[int]) -> bytes:
    return u32(len(values)) + u32s(values)


# 因子关卡列表：45543，body=[start][end]（lxy_yz/factor_write_only 实证：分页查询 [0,999] / [1000,1999]）
STAGE_LIST = 45543


def stage_list_step(start: int, end: int) -> FeatureStep:
    return FeatureStep("因子关卡列表", STAGE_LIST, u32(start) + u32(end), False, "STAGE_LIST")


@dataclass(slots=True)
class FeatureStep:
    name: str
    cmd: int
    body: bytes
    write: bool = False
    note: str = ""


def bag_steps(
    *,
    pet_id: int | None = None,
    item_ids: list[int] | None = None,
    forever_ids: list[int] | None = None,
    cloth_ids: list[int] | None = None,
    title_id: int | None = None,
) -> list[FeatureStep]:
    """精灵背包 / 装备。参数为 None 的步骤不发送。"""
    steps = [
        FeatureStep("打开背包", 43706, b"", False, "GET_PET_INFO_BY_ONCE"),
    ]
    if forever_ids is not None:
        steps.append(FeatureStep("加载配置", 46046, list_body(forever_ids), False, "GET_MULTI_FOREVER"))
    if item_ids is not None:
        steps.append(FeatureStep("装备列表", 42399, list_body(item_ids), False, "MULTI_ITEM_LIST"))
    if pet_id is not None:
        steps.append(FeatureStep("精灵信息", 2301, u32(pet_id), False, "GET_PET_INFO"))
    if cloth_ids is not None:
        steps.append(FeatureStep("切换装扮", 2604, list_body(cloth_ids), True, "CHANGE_CLOTH"))
    if title_id is not None:
        steps.append(FeatureStep("设置称号", 3404, u32(title_id), True, "SETTITLE"))
    return steps


def factor_steps(
    *,
    item_ids: list[int] | None = None,
    factor_ids: list[int] | None = None,
    pet_id: int | None = None,
    factor_id: int | None = None,
    action: tuple[int, int] = (1, 0),
) -> list[FeatureStep]:
    """精灵因子关卡：列表 → 因子信息 → 进图 → 因子动作。

    注意：这是复合动作，装备切换/精灵选择/选关卡的组合由调用方决定。
    """
    steps: list[FeatureStep] = []
    if item_ids is not None:
        steps.append(FeatureStep("因子道具", 42399, list_body(item_ids), False, "MULTI_ITEM_LIST"))
    steps.append(FeatureStep("打开背包", 43706, b"", False, "GET_PET_INFO_BY_ONCE"))
    if factor_ids is not None:
        steps.append(FeatureStep("因子信息", 46046, list_body(factor_ids), False, "GET_MULTI_FOREVER"))
    if pet_id is not None:
        steps.append(FeatureStep("选择精灵", 2301, u32(pet_id), False, "GET_PET_INFO"))
    steps.append(FeatureStep("进入地图", 2001, b"", False, "ENTER_MAP"))
    if factor_id is not None:
        steps.append(
            FeatureStep(
                "因子动作",
                41413,
                u32(factor_id) + u32(action[0]) + u32(action[1]),
                True,
                "因子关卡/领取",
            )
        )
    return steps


# 直接复刻抓包中的两组序列，便于回归测试
CAPTURE_EQUIP = bag_steps(
    pet_id=0x6ACE3260,
    item_ids=[
        0x00049422, 0x00155E20, 0x001A0DF7, 0x001A0BAF, 0x001A0BB0, 0x001A0BAE,
        0x0004942B, 0x00049681, 0x00049468, 0x00049421, 0x0004941F, 0x00155D5A,
        0x001A45A1, 0x001A44D6, 0x001A52BB, 0x001A488A, 0x00155D59, 0x00155D58,
        0x001A4214, 0x000496C6, 0x0004967F, 0x00049699, 0x00231865, 0x00231866,
        0x00231867, 0x00231868, 0x00231871, 0x00231883, 0x00231884,
    ],
    forever_ids=[0x00000B05, 0x0001E4B6],
    cloth_ids=[0x0013D8BE, 0x0013DA30, 0x0013D8C0, 0x0013D8BF, 0x0013D8C1],
    title_id=0x1A1,
)

CAPTURE_FACTOR = factor_steps(
    item_ids=[0x0024A163],
    factor_ids=[0x0004A0AA, 0x0004A0AB, 0x0004A0A8, 0x0001ECE8],
    pet_id=0x6ACE3260,
    factor_id=0x0024A052,
    action=(1, 0),
)


def format_steps(steps: list[FeatureStep], *, dry_run: bool = True) -> str:
    lines = []
    for i, s in enumerate(steps, 1):
        tag = "WRITE" if s.write else "READ"
        if s.write and dry_run:
            tag = "DRY-WRITE"
        lines.append(f"{i:02d} {tag} cmd={s.cmd} len={len(s.body)} {s.name} {s.note} body={s.body.hex()}")
    return "\n".join(lines)


def _id_list(body: bytes) -> list[int]:
    if len(body) < 4:
        return []
    count = struct.unpack(">I", body[:4])[0]
    ids = []
    for off in range(4, min(len(body), 4 + count * 4), 4):
        ids.append(struct.unpack(">I", body[off:off + 4])[0])
    return ids


def _resolve(provider: object, obj_id: int, resources: tuple[str, ...]) -> str:
    for res in resources:
        try:
            name = provider.name(res, obj_id)
        except Exception:
            name = None
        if name:
            return f"{name}[{obj_id}]"
    return hex(obj_id)


def readable_steps(
    steps: list[FeatureStep],
    *,
    provider: object | None = None,
    dry_run: bool = True,
) -> list[str]:
    out = []
    for i, s in enumerate(steps, 1):
        tag = "WRITE" if s.write else "READ"
        if s.write and dry_run:
            tag = "DRY-WRITE"
        if provider is None:
            detail = s.body.hex()
        elif s.cmd in (42399, 2604, 46046):
            ids = _id_list(s.body)
            resolve_res = ("item", "factor", "pet", "equip")
            detail = ", ".join(_resolve(provider, x, resolve_res) for x in ids) or "(空)"
        elif s.cmd == 3404:
            ids = _id_list(s.body)
            detail = _resolve(provider, ids[0], ("title", "item")) if ids else "(空)"
        elif s.cmd == 2301:
            ids = _id_list(s.body)
            detail = _resolve(provider, ids[0], ("pet", "item")) if ids else "(空)"
        elif s.cmd == 41413:
            ids = _id_list(s.body)
            if ids:
                factor = _resolve(provider, ids[0], ("factor", "item"))
                detail = f"{factor} action={ids[1]}/{ids[2]}" if len(ids) >= 3 else f"{factor}"
            else:
                detail = "(空)"
        else:
            detail = s.body.hex() if s.body else "(空)"
        out.append(f"{i:02d} {tag} cmd={s.cmd} {s.name} -> {detail}")
    return out