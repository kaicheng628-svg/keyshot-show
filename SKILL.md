---
name: keyshot-show
description: 将 KeyShot 的 KSP/BIP 场景制作成 360 度转台或环绕展示视频，保留场景材质与灯光，支持预览检查、分批续渲及 MP4 验证。用于 KeyShot 模型展示视频、旋转一圈或几秒的产品演示，不用于从单张图片猜测三维背面。
---

# keyshot show

从用户提供的 KeyShot 场景输出真实逐帧渲染的展示视频。通常采用相机围绕模型中心旋转，保留原模型、材质、光照和背景。用户明确要求物体旋转、固定背景或固定灯光相对相机时，应调整方案，不把相机环绕当作完全相同的效果。

## 输入和默认值

优先使用已有任务信息。未指定时默认：每个模型单独一段 MP4，4 秒，1920×1080，30 fps，水平绕世界 Y 轴一圈，沿用原相机俯仰角，64 samples 起步。用户要求优先，不必再次确认已授权的制作工作。

先查看工作目录内 `.ksp` / `.bip`、KeyShot 版本和可用渲染能力。保护原始文件；使用任务专属输出目录，不覆盖现有成品。加载输入会替换当前场景，先保护用户原有未保存工作，不能直接丢弃未知更改。

## 工作流

1. **准备配置。** 读 [操作与配置](references/workflow.md)，建立 `job.json`。定位 KeyShot 与 FFmpeg/FFprobe，不假定案例安装路径。需要 Windows UI 操作时加载当前环境的 `computer-use` 技能，遵守其 API。原生 KeyShot Python 负责场景，外部 Python 负责文件校验和编码。
2. **验证模式。** GPU 模式先在 KeyShot「渲染 → 选项」选中「最大采样」，脚本仍显式传入采样选项。首次输出失败就停止批量流程，按参考文档处理；不以“执行完毕”代替文件成功。
3. **八方向预览。** 执行 `render_keyshot.py` 的 `run(config_path, mode='preview')`，再用 `encode_video.py --preview` 生成接触表并实际查看。检查所有朝向居中、完整入镜及光照背景。`distance_scale=1.25` 是案例起点，不是通用保证。取景调整后重新预览，再开始正式帧。
4. **正式逐帧渲染。** `N = duration × fps`，角度为 `0 … 360×(N−1)/N`，不重复末尾 360° 帧。相机位置、方向和 up 向量围绕同一固定中心同步旋转；只旋转 direction 会把模型移出画面。
5. **分批续渲。** 默认每次最多新渲染 60 帧，返回 `batch_complete`。这是 8GB 显卡案例的保守起点，可按显存和速度调整。续跑相同命令会跳过已验证帧。连续渲染明显变慢或显存接近上限时，在批次边界正常重启 KeyShot，恢复最大采样再续渲。不要假设 `newScene()` 或重载文件能释放 GPU 缓存。
6. **合成验证。** 帧齐全后运行 `encode_video.py`，输出 H.264/yuv420p MP4、接触表和报告。实际查看全部角度及首尾接续；确认每帧有效、尺寸、帧率、帧数、时长和完整解码通过。必要时播放成片。解码通过不能代替画面检查。
7. **交付。** 给出成品链接及参数。保留原始工程和续渲文件。不要自动删除帧、关闭其他应用或改系统性能设置。

## 脚本

- [keyshot_job.py](scripts/keyshot_job.py)：配置、源文件指纹、PNG 完整性检查和环绕数学。
- [render_keyshot.py](scripts/render_keyshot.py)：KeyShot 内的预览、渲染、原子提交帧、批次边界、STOP 文件和进度。
- [encode_video.py](scripts/encode_video.py)：外部 Python 的帧校验、接触表、MP4 编码和验证，依赖 Pillow、FFmpeg、FFprobe。

配置、UI 入口、常见问题和验证范围见 [操作与配置](references/workflow.md)。依赖不可用时说明限制，不伪造输出或擅自换软件重建外观。
