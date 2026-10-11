# 操作与配置

## 任务配置

将下面配置保存到任务目录的 `job.json`。路径须为绝对路径，Windows JSON 可用 `/`。id 是唯一的安全文件名，不要求等于源文件名。

```json
{
  "work_dir": "C:/KeyShotShow/work",
  "output_dir": "C:/KeyShotShow/output",
  "duration": 4,
  "fps": 30,
  "width": 1920,
  "height": 1080,
  "samples": 64,
  "preview_samples": 32,
  "distance_scale": 1.25,
  "axis": "y",
  "direction": -1,
  "engine": "gpu",
  "max_frames_per_run": 60,
  "ffmpeg": "C:/Tools/ffmpeg/bin/ffmpeg.exe",
  "ffprobe": "C:/Tools/ffmpeg/bin/ffprobe.exe",
  "models": [
    {"id": "model-a", "source": "C:/KeyShotShow/models/model-a.ksp"},
    {"id": "model-b", "source": "C:/KeyShotShow/models/model-b.ksp"}
  ]
}
```

单个 model 可设置 distance_scale 和 `pivot: [x,y,z]`，默认中心为原相机 look-at。axis 可为 x/y/z，按实际朝上方向选择；direction 为 −1 或 1，规定数学旋转方向，不能脱离观察方向简单称为顺/逆时针。engine 为 gpu/cpu。宽高须为偶数，fps 为正整数，duration×fps 须为整数。

任务指纹包含源文件 SHA256 和影响画面的配置。正式帧开始后，更换输入或参数应使用新的 work_dir，防止混入旧帧。BIP 的外部贴图无法只靠 BIP 哈希跟踪：优先自带依赖的 KSP；用 BIP 时保持引用资源不变，资源改变也要建立新任务。

## KeyShot 入口

案例验证于 Windows KeyShot Studio 2025.1 GUI、RTX 4060 Laptop 8GB。此机 headless 返回无法初始化许可，GUI 正常；无需反复尝试不可用的 headless，不能修改或绕过许可。

1. 保护用户当前未保存场景后再载入输入。
2. 「渲染」窗口（此版本 Ctrl+P）→「选项」→质量「最大采样」。确认选中，再关闭设置窗口。
3. 「窗口」→「脚本控制台」。点击底部单行输入框，输入以下一行再按 Return。不要用 Tab 聚焦，它可能插入缩进，造成 IndentationError。

```python
import runpy; runpy.run_path(r'C:\Tools\keyshot-show\scripts\render_keyshot.py', init_globals={'lux': lux})['run'](r'C:\KeyShotShow\job.json', mode='preview')
```

正式渲染改为 `mode='render'`，每批及重启后用相同命令。路径使用实际安装位置。UI 坐标及元素编号须来自当次截图/树，不沿用案例坐标。遵循 computer-use 技能，不用 PowerShell UI Automation 绕过。

### GPU 采样问题

此版本案例中，UI 停留在「自定义控制」时，脚本设置 samples 仍可能报“请选择最大采样或最大时间”。重启或 newScene 后也观察到设置重置。成功方式是 UI 最大采样，加脚本中 getRenderOptions().getDict() → 更新 render_mode / progressive_max_samples → RenderOptions(dict=rd) → setMaxSamplesRendering(samples)，并关闭队列及后台渲染。

省略 opts 曾返回失败而不抛异常，不可用此法规避错误。渲染脚本检查返回值、完整 PNG 和尺寸，再原子重命名提交。

## 预览和编码

外部 Python 需 Pillow；通过工作区依赖工具定位运行时，不假定系统 Python 自带。以下在外部 PowerShell 执行，不在 KeyShot 控制台启动系统 shell。

```powershell
& '<Python绝对路径>' '<技能目录>/scripts/encode_video.py' '<任务目录>/job.json' --preview
& '<Python绝对路径>' '<技能目录>/scripts/encode_video.py' '<任务目录>/job.json'
```

preview 只生成八方向接触表；正式编码生成 MP4、最多 12 方向接触表和 verification.json。只合成某个已完成模型可加 `--model '模型id'`。默认要求所选模型帧完整，不默默漏掉未完成模型。已有输出拒绝覆盖，先查文件与报告，再选择新输出目录或明确处理旧成品。

查看预览的边缘留白、所有朝向、透明材质和细线、地面与阴影。正式开始后测一帧实际分辨率，再用近期帧耗时给估计，不能仅用低分辨率预览估计。补帧、静态图扭曲和图片旋转不能冒充真实 360° 渲染。

## 进度与恢复

work_dir/progress.json 包含 status、mode、completed、total、model/frame、本批耗时和单帧耗时。complete 仅表示该模式的帧齐全，视频还需编码验证。batch_complete 是正常续渲边界。

在 work_dir 创建空 STOP 文件，会在下一帧开始前停止；当前帧先保存，状态为 stopped。确认停止后删除标记，重跑相同命令。不能把内部维护暂停说成用户取消，也不要渲染中修改配置或并行复用工作目录。

可只读执行 `nvidia-smi --query-gpu=memory.used,utilization.gpu,temperature.gpu --format=csv`。案例中长期逐帧调用后显存从约 2GB 到 7.9GB，单帧从约 4 秒到二十多秒；重载场景未释放，正常退出 GUI 后降至约 0.4GB，重启恢复速度。这是诊断线索，不是所有机器的通用阈值或必然泄漏。批次边界重启任务所用 KeyShot，保护用户工作，仅可丢弃确认属于助手的临时相机更改。重启后恢复最大采样再续渲。

同一错误修正后再失败两次，应检查版本、UI 模式和 API，停止相同无效重试；保留帧及错误报告并说明限制，不能只留下脚本就宣称完成。

## 验证范围和资料

原流程实机完成两个 KSP 的视频；参数化技能随后也完成了第三个 KSP。三个视频均为 120 帧、1920×1080、30fps、4.000 秒，完整解码及角度接触表检查通过。实机记录不代表所有 KeyShot 版本均兼容；首次新场景必须预览。

修改脚本后可在外部 Python 运行 `scripts/test_workflow.py --ffmpeg <路径> --ffprobe <路径>`。它使用临时目录和模拟 lux，不操作真实 KeyShot 场景；覆盖环绕中心、独立角度、预览、批次、续渲、损坏帧恢复、参数指纹隔离、STOP、失败输出拒绝、相机恢复与禁止覆盖，并实际调用 FFmpeg/FFprobe 验证 4 秒 MP4 编码和完整解码。

- [KeyShot 2025.1 Python API](https://media.keyshot.com/scripting/doc/2025.1/lux.html)：场景、相机、renderImage、RenderOptions。
- [Scripting quick start](https://manual.keyshot.com/keyshot11/manual/scripting/quick-start-scripting/)：控制台概念，具体 UI 以当前版本为准。
