# keyshot show

将 KeyShot `.ksp` / `.bip` 场景制作成真实逐帧渲染的 360° 模型展示视频，可作为 Codex 技能使用，也可手动运行脚本。

默认每个模型输出 **4 秒、1920×1080、30fps、120 帧的 MP4**。沿用场景材质、灯光与背景，通过相机围绕固定中心旋转展示模型。

## 功能

- 八方向低分辨率预览，先检查整圈构图。
- 相机位置、方向与 up 向量同步旋转，保持固定环绕中心。
- 默认每批最多渲染 60 帧，重复执行可续渲，并重新生成损坏的帧。
- 按输入文件和参数指纹隔离帧，支持 STOP 标记与进度报告。
- H.264 / yuv420p 编码，核验尺寸、帧率、帧数、时长和完整解码。
- 多模型批量处理，保留原始工程，拒绝覆盖现有视频。

## 运行环境

实机验证环境为 Windows、KeyShot Studio 2025.1、RTX 4060 Laptop 8GB。需要可正常使用脚本与渲染功能的 KeyShot 安装及许可；其他版本需要先验证 API 和预览。

- **KeyShot 内置 Python**：执行场景加载和逐帧渲染，使用原生 `lux` API。
- **外部 Python 3.10 或更高版本与 Pillow**：检查图像、生成接触表并调用视频编码工具。
- **FFmpeg / FFprobe**：FFmpeg 需包含 `libx264` 编码器。
- 使用 Codex 控制 Windows 界面时，还需要可用的 computer-use 能力。

GitHub 用来保存和分享工作流；渲染在安装了 KeyShot 的本地电脑上运行。

## 获取与安装

点击本仓库 **Code → Download ZIP**，解压后保留目录结构；也可克隆：

```powershell
git clone https://github.com/kaicheng628-svg/keyshot-show.git
cd keyshot-show
python -m pip install -r requirements.txt
```

作为 Codex 技能使用时，可将仓库链接交给 Codex，要求安装仓库中的 `keyshot-show` 技能。技能入口是仓库根目录的 `SKILL.md`，配套目录必须一并保留。调用示例：

> 使用 $keyshot-show，把指定文件夹中的 KeyShot 场景制作成 4 秒、1080p、30fps 的 360 度展示视频。

已有本机安装无需重复安装。手动运行脚本可按下方步骤进行。

## 手动使用

### 1. 准备任务配置

复制 [examples/job.example.json](examples/job.example.json) 到独立任务目录，重命名为 `job.json`。修改模型文件、工作目录、输出目录及 FFmpeg / FFprobe 的绝对路径。示例路径仅为占位，不会自动发现软件。

每个模型的 `id` 必须是唯一且可用作文件名的名称。优先使用打包好资源的 KSP；使用 BIP 时须保证外部贴图等引用资源可用。

### 2. 在 KeyShot 中渲染预览

保护当前未保存场景。在 KeyShot 的“渲染 → 选项”中选择“最大采样”，然后打开“窗口 → 脚本控制台”。把下面两个路径换成实际位置，在控制台运行这一行：

```python
import runpy; runpy.run_path(r'C:\Tools\keyshot-show\scripts\render_keyshot.py', init_globals={'lux': lux})['run'](r'C:\KeyShotShow\job.json', mode='preview')
```

在外部 PowerShell 生成预览接触表：

```powershell
python C:\Tools\keyshot-show\scripts\encode_video.py C:\KeyShotShow\job.json --preview
```

打开命令返回的 `contact.jpg`，确认八个方向均完整入镜。需要调整时修改 `distance_scale` 或 `pivot` 后重新预览。`distance_scale=1.25` 只是起点。

### 3. 渲染正式帧并续渲

在 KeyShot 控制台运行相同命令，把 `mode='preview'` 改成 `mode='render'`。默认每批 60 帧；返回 `batch_complete` 后再次执行，直到 `complete`。

`work_dir/progress.json` 提供当前进度。`complete` 仅表示帧渲染完成，仍需要下一步编码。若显存持续增长、渲染明显变慢，在批次边界正常重启 KeyShot，恢复“最大采样”后继续运行。

### 4. 编码并检查视频

```powershell
python C:\Tools\keyshot-show\scripts\encode_video.py C:\KeyShotShow\job.json
```

默认输出 `<模型id>_360_4s.mp4`；帧目录内保存 `contact.jpg` 和 `verification.json`。除自动检查外，还应查看视频的全角度构图及首尾衔接。

更多参数、暂停恢复及故障处理见 [操作与配置](references/workflow.md)。

## 验证

原流程及参数化技能已在上述实机环境完成三个 KSP 场景，均生成 4 秒、1080p、30fps、120 帧视频，并通过完整解码和角度接触表检查。模型与成片不随本仓库发布。

可运行现有离线测试，验证环绕、分批、续渲、损坏帧修复、参数隔离、STOP、失败处理、相机恢复及实际视频编码：

```powershell
python scripts/test_workflow.py --ffmpeg C:\Tools\ffmpeg\bin\ffmpeg.exe --ffprobe C:\Tools\ffmpeg\bin\ffprobe.exe
```

测试使用模拟 `lux`，不会操作真实 KeyShot 场景；不能替代新版本、新模型的预览检查。

## 文件结构

```text
SKILL.md                 Codex 技能入口
agents/openai.yaml       技能显示信息
references/workflow.md   详细操作与故障处理
examples/job.example.json 示例任务配置
scripts/keyshot_job.py   配置、指纹、PNG 校验、环绕数学
scripts/render_keyshot.py KeyShot 内的渲染与续渲
scripts/encode_video.py  接触表、编码与视频验证
scripts/test_workflow.py 离线行为和编码测试
```

工作流采用相机环绕；物体转台在固定灯光下旋转时，反射和背景的表现可能不同。需要物体自身旋转时，应另行调整动画方案。
