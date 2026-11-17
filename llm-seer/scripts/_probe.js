// 最小探测脚本：验证 2.0.9 能否直接运行明文 JS
// 用法：复制到 F:\seer\Script\，在雷小伊「脚本」页刷新/选中后运行
function main() {
  println("[probe] hello from js");
  for (let i = 0; i < 3; i++) {
    println("[probe] tick " + i);
    Sleep(500);
  }
  println("[probe] done");
}
main();