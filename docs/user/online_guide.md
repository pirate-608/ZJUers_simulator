# 在线游戏

<div class="zjus-video-showcase">
  <figure>
    <video controls preload="metadata" playsinline src="/assets/videos/zjus-demo1.mp4"></video>
    <figcaption>游戏流程演示（一）</figcaption>
  </figure>
  <figure>
    <video controls preload="metadata" playsinline src="/assets/videos/zjus-demo2.mp4"></video>
    <figcaption>游戏流程演示（二）</figcaption>
  </figure>
</div>

## 游戏入口

访问 [67656.fun](https://67656.fun)。

首次访问会先播放一段可跳过的序章。播放结束或点击“跳过”后，浏览器会记住该状态，后续刷新或返校登录会直接进入登录页。

## 新玩家流程

1. 在首页填写昵称和邀请码。
2. 可选：展开“自定义大模型”并填写本次会话使用的模型配置。
3. 登录成功后保存系统生成的“学生凭证”，之后老玩家登录会用到。
4. 选择专业。
5. 分配初始属性：`IQ`、`EQ`、`Luck`、`魅力` 四项总点数必须等于 `300`，每项范围为 `50-150`。
6. 确认创建角色后进入游戏。

::: tip
专业会额外提供 IQ 增益，因此角色创建页中的 300 点预算只计算你手动分配的基础值。

:::
## 老玩家流程

1. 填写原昵称、邀请码和学生凭证。
2. 登录成功后选择“加载已有存档”或“开始新游戏”。
3. 加载存档会恢复上次保存的专业、课程、属性和进度；开始新游戏会重新进入角色创建。

## 游戏界面

进入游戏后会看到课程列表、中央面板、属性面板和右侧操作区。中央面板可以在“求是园动态”“钉钉”和“道具”之间切换；收到钉钉消息后，对应角色会出现在联系人列表中；道具页可以用金币购买或出售持有即生效的加成道具。内容生成模式可在右侧切换，详见[内容生成模式](./content_modes.md)。

首次进入主界面会显示新手引导；引导期间游戏会暂停，学期倒计时、精力消耗、随机事件和钉钉消息都不会继续结算。

随机事件选择结果、刷 CC98、健身、散步和开黑的结果会同时写入“求是园动态”日志，并以弹窗显示。随机事件结果弹窗 5 秒后自动关闭，休闲动作结果弹窗 3 秒后自动关闭，均可手动关闭。

钉钉联系人有新消息时会显示红点；支持回复的角色会在私聊底部显示回复选项。更多说明见[钉钉私聊](./dingtalk.md)。

右侧休闲动作有独立冷却。冷却中按钮会锁定并显示剩余秒数；暂停时休闲、课程策略、期末考试、道具买卖等主要操作也会锁定。

文档首页提供可交互的游戏 Demo，可直接查看主界面、课程、求是园动态和钉钉私聊的基本效果。

<style scoped>
.zjus-video-showcase {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 16px;
  margin: 18px 0 30px;
}

.zjus-video-showcase figure {
  margin: 0;
}

.zjus-video-showcase video {
  display: block;
  width: 100%;
  border: 1px solid var(--vp-c-border);
  border-radius: 8px;
  background: #000;
}

.zjus-video-showcase figcaption {
  margin-top: 8px;
  color: var(--vp-c-text-2);
  font-size: 0.9rem;
  text-align: center;
}

@media (max-width: 760px) {
  .zjus-video-showcase {
    grid-template-columns: 1fr;
  }
}
</style>
