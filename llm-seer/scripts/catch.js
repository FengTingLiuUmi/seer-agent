// 野怪捕捉脚本（完全按雷小伊 JS 文档的 API 写）
// 目标：进指定地图 → 监听 2004 野怪刷新 → 命中目标 id → Fight("2408,槽位")
// 依赖：雷小伊 2.0.9 脚本引擎（Send / CmdManager / Fight / Pet_GetName / IsRunning / Sleep）

var MAP_ID = 3001;        // 目标地图（按需修改）
var MAP_X = 725;
var MAP_Y = 272;
var WANT = [164];         // 要捕捉的野怪 id（按需修改）

function main() {
  println("[catch] enter map " + MAP_ID);
  Send("2002");                       // 离开当前地图
  Sleep(800);
  Send("2001,0," + MAP_ID + "," + MAP_X + "," + MAP_Y);
  Sleep(1500);

  var stop = false;

  CmdManager.add(2004, function (ret) {
    if (ret.errID != 0) { return; }
    for (var i = 0; i < 9; i++) {
      var petId = ret.data.readUnsignedInt();
      if (petId == 0) { continue; }
      println("[catch] slot " + i + " -> " + petId + " " + Pet_GetName(petId));
      for (var k = 0; k < WANT.length; k++) {
        if (petId == WANT[k]) {
          println("[catch] fight slot " + i);
          Fight("2408," + i, "捕捉精灵.afc");
          stop = true;
          return;
        }
      }
    }
  });

  while (IsRunning() && !stop) { Sleep(500); }
  CmdManager.del(2004);
  println("[catch] end");
}

main();