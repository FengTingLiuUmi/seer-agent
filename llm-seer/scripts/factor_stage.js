// 精灵因子关卡（通用“关卡战斗”脚本骨架，按雷小伊对战文档 API 写）
// 流程：进关卡 → Send("2415") 开始战斗 → 每回合 onFightEvent 决策 → 胜利/失败处理
// 说明：技能 id 先用技能列表里的第一个（可从 data.useSkill.my.skillInfo 读到），后续可替换为策略

var STAGE_SKILLS = [];   // 想固定出招就填技能 id；空 = 用第一个 PP>0 的技能

function pickSkill(my) {
  if (!my || !my.skillInfo) { return 0; }
  for (var i = 0; i < my.skillInfo.length; i++) {
    var s = my.skillInfo[i];
    if (s && s.id && s.pp > 0) {
      if (STAGE_SKILLS.length == 0) { return s.id; }
      for (var k = 0; k < STAGE_SKILLS.length; k++) {
        if (s.id == STAGE_SKILLS[k]) { return s.id; }
      }
    }
  }
  return 0;
}

function onFightEvent(data) {
  var my = data.useSkill && data.useSkill.my;
  var other = data.useSkill && data.useSkill.other;
  if (!my) { return false; }

  if (data.round == 0) {
    println("[stage] round0 登场：我方 " + my.pid + " hp " + my.hp + "/" + my.maxHp +
            " 敌方 " + (other ? other.pid : "?") + " hp " + (other ? other.hp : "?"));
    return false;
  }

  println("[stage] R" + data.round + " my " + my.hp + "/" + my.maxHp +
          " other " + (other ? other.hp : "?") + "/" + (other ? other.maxHp : "?"));

  if (my.hp <= 0) {
    return false;              // 交给框架换精灵
  }
  var sid = pickSkill(my);
  if (sid) {
    useSkill(sid);
    return true;               // 已操作，框架不再自动出招
  }
  return false;
}

function main() {
  println("[stage] start fight level");
  Send("2415");                // START_FIGHT_LEVEL（无参）
  while (IsRunning()) { Sleep(500); }
  println("[stage] end");
}

main();