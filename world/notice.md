# 折姜大学招生减章
## 1.这是一个可能还有很多bug的游戏，不过好在代码用MIT证书完全开源，来得及被修复（？）
*   [访问GitHub项目仓库](https://github.com/pirate-608/ZJUers_simulator.git)
*   或直接：

```Powershell
git clone https://github.com/pirate-608/ZJUers_simulator.git
```

## 2.该游戏仅供娱乐，不提供对任何学校、组织或个人的教育、学习和工作参考

## 3.项目暂不支持稳定的公网部署
如有需求，可自行克隆代码后配置Cloudflare Tunnel，访问[Cloudflare Zero Trust](https://one.dash.cloudflare.com/)查看详情

## 4.游戏的简化处理
由于大类招生政策引入大量复杂因素，不利于游戏的数据流处理，该项目简化为开局直接随机分配专业，并根据json格式的“培养方案”文件进行游戏循环。详情请查看[培养方案列表](http://localhost:8000/world/courses/)，若返回404，可以直接查看项目根目录下的world/courses目录。

## 5.贡献
1.改进和优化代码、增加和完善功能：欢迎Pull Request
2.补充设定、提供资料：欢迎丰富world目录下的内容，尤其是keywords和characters（请注意格式）。