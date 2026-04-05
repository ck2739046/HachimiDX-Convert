读取本工作区github仓库的commit历史, 还要知道 tag v0.0.2 对应哪个 commit。

从 tag v0.0.2 为起点，一直到现在最新 commit 为终点，你需要逐个读取这之间的所有commit的信息 (不用阅读具体代码diff，仅标题、描述即可)，总结出修改了什么。

如果多个commit修改的内容是为了实现同一个fetaure，可以合并总结为一条。
我需要编写brief changelog。
你要提供中文和英语两版，创建changelog.md

PowerShell 读取中文 commit message 容易乱码；先设置 $OutputEncoding 与 [Console]::OutputEncoding 为 UTF-8，再执行 git log。

使用 git -c i18n.commitEncoding=utf-8 -c i18n.logOutputEncoding=utf-8 可稳定输出可读中文日志。
