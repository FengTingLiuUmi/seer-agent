// 状态探测脚本：确认数据类 API 可用（安全、不发任何包）
// 在「自定义脚本(测试阶段)」窗口里贴入运行

function main() {
  println("[state] start");

  // 1) 精灵信息（用鲁斯王 4648 举例；找不到就换你有的）
  try {
    var ct = Pet_GetCatchtime(4648);
    println("[state] Pet_GetCatchtime(4648) = " + ct);
    if (ct) {
      println("[state] Pet_GetName = " + Pet_GetName(4648));
      println("[state] Pet_GetInfo = " + JSON.stringify(Pet_GetInfo(ct)));
    } else {
      println("[state] 没找到 4648，试试 Pet_GetCatchtimes");
    }
  } catch (e) {
    println("[state] pet api err: " + e);
  }

  // 2) 物品
  try {
    println("[state] Item_GetName(1300673) = " + Item_GetName(1300673));
    println("[state] Item_GetNum(1300673) = " + Item_GetNum(1300673));
  } catch (e) {
    println("[state] item api err: " + e);
  }

  // 3) 永久/每日值（试几个 key）
  try {
    var arr = GetForverOrDailyValue([1, 2, 3]);
    println("[state] GetForverOrDailyValue([1,2,3]) = " + JSON.stringify(arr));
  } catch (e) {
    println("[state] value api err: " + e);
  }

  println("[state] done");
}
main();