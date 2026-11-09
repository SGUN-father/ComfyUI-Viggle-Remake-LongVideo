# ComfyUI Viggle Remake Long Video

让 Viggle Remake 视频换人支持长视频（15～20 秒以上）的 ComfyUI 节点包。可以和官方 Viggle 节点包同时安装，也可以单独使用。
A ComfyUI node pack that lets Viggle Remake swap people in long videos (15–20 s and more). Works next to the official Viggle pack or on its own.

## 节点 / Nodes

| 节点 / Node | 功能 / What it does |
|---|---|
| **Viggle Remake Conditioning** | 把源视频、参考图、提示词和原音频编码成条件，`frames` 最多 10000 帧（官方是 345），长视频可以直接用。 / Encodes the source video, reference images, prompt and soundtrack; `frames` up to 10000 (official: 345). |
| **Viggle Remake Noise** | 按官方参考脚本的顺序生成初始噪声，同一个 seed 出同样的视频。 / Draws the starting noise in the reference script's order, so a seed gives the same video. |
| **Viggle Remake Long Video** | 关键帧撤除 + H3 上下文窗口 + 按窗口切源视频，一个节点完成长视频分窗口生成。 / Keyframe Until + H3 context windows + per-window source slicing in one node. |

### Long Video 节点做什么 / What the Long Video node does

1. **Keyframe until**：sigma 低于 `keyframe_until` 后撤掉关键帧，和官方节点逻辑一样。
   Drops the keyframes below `keyframe_until`, same as the official node.
2. **Context windows**：直接调用 ComfyUI 自带的 `MiniMax H3 Context Windows`，把长视频分窗口生成。
   Calls ComfyUI's own `MiniMax H3 Context Windows` to render the video window by window.
3. **Slice source**：官方窗口只切目标画面，不切源视频，后面的窗口会重复开头的动作。这一步让每个窗口只看到自己那一段源视频。用的是 ComfyUI 窗口的官方回调接口，不改 ComfyUI 的任何文件。
   The official windows slice only the target, not the source clip, so later windows repeat the opening. This step gives each window only its own part of the source, through the context handler's official callbacks. Nothing in ComfyUI is patched.

## 安装 / Install

1. 需要 **ComfyUI 0.44.0 或更新**（带 MiniMax H3 上下文窗口）。 / Needs **ComfyUI 0.44.0+** (MiniMax H3 context windows).
2. 把本文件夹放进 `ComfyUI/custom_nodes/`，重启。 / Put this folder in `ComfyUI/custom_nodes/` and restart.
3. 模型按官方说明下载：H3 fl2va 底模 + Viggle swap LoRA（用 `LoraLoaderBypassModelOnly` 加载）、qwen3vl 文本编码器、视频和音频 VAE，见 [Viggle/Viggle-Remake](https://huggingface.co/Viggle/Viggle-Remake) 的 `COMFYUI.md`。
   Models as in the official `COMFYUI.md`.

## 用法 / Usage

```
模型 + LoRA → Viggle Remake Long Video → BasicGuider ─┐
Viggle Remake Conditioning → positive → BasicGuider     ├→ SamplerCustomAdvanced
                                  → positive → Viggle Remake Noise
                                  → latent ─────────────────────┘
```

示例工作流在 `example_workflows/`。 / See `example_workflows/`.

| 参数 / Input | 默认 / Default | 说明 / Notes |
|---|---|---|
| keyframe_until | 0.9 | 保持 0.9 / keep 0.9 |
| context_length | 124 | 窗口帧数，17n+5（124 ≈ 5.2 秒） / window frames, 17n+5 |
| context_overlap | 39 | 重叠帧数，17n+5 / overlap, 17n+5 |
| fuse_method | pyramid | 窗口融合方式 / blending |
| freenoise | true | 改善窗口衔接 / better blending |
| split_conds_to_windows | false | Viggle 用不到，保持关闭 / leave off |
| slice_source | true | 每个窗口只看自己那段源视频；关掉 = 官方原样行为 / off = plain official behaviour |

`frames` 必须是 17n+5，示例工作流用数学节点把视频总帧数向下取成 17n+5。
`frames` must be 17n+5; the example workflow rounds the video's frame count down with a math node.

## 许可 / License

Apache-2.0，见 `LICENSE` 和 `NOTICE`。包含源自 Viggle Remake 官方 ComfyUI 节点包的代码（Apache-2.0，© 2026 Viggle AI）。模型权重不在本仓库内，按 MiniMax H3 Community License 分发。
Apache-2.0, see `LICENSE` and `NOTICE`. Contains code derived from the official Viggle Remake ComfyUI pack (Apache-2.0, © 2026 Viggle AI). Model weights are not included.

Powered by [Viggle Remake](https://huggingface.co/Viggle/Viggle-Remake)
