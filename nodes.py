# SPDX-License-Identifier: Apache-2.0
"""Viggle Remake Long Video (by神棍)

One node that replaces this three-node chain of the long-video Viggle Remake workflow:

    Viggle Remake Keyframe Until  ->  MiniMax H3 Context Windows  ->  Slice Source By Window

1. Keyframe until   drops the keyframes once sigma falls below `keyframe_until` (same as the official
                    "Viggle Remake Keyframe Until").
2. Context windows  calls ComfyUI's own "MiniMax H3 Context Windows" node, so the window maths stays
                    whatever the installed ComfyUI does.
3. Slice source     the official window node only slices the target latents; the source clip passed as
                    <Video 1> stays whole, so every later window copies the start of the source. This
                    step cuts the source reference block to each window's latent indices, through the
                    context handler's official callbacks (nothing in ComfyUI is patched).

Use it with "Viggle Remake Conditioning by神棍" + "Viggle Remake Noise by神棍" from this pack (the official
Conditioning + Noise work too). It does not touch the official pack.
Needs ComfyUI 0.44.0 or newer (MiniMax H3 context windows).
"""

import comfy.context_windows
import comfy.patcher_extension

_KEY = "viggle_remake_longvideo_by_shengun"


# ---------------------------------------------------------------- 1. keyframe until
def _make_keyframe_release(keyframe_until):
    # identical logic to the official RemakeKeyframeUntil node (Viggle, Apache-2.0)
    def release(executor, x, timestep, context, transformer_options, minimax_payload=None, **kwargs):
        p = minimax_payload or {}
        if p.get("keyframes") and float(timestep.flatten()[0]) / 1000 < keyframe_until:
            refs = p.get("refs") or []
            minimax_payload = dict(p, keyframes=None, layout=None,
                                   cond_video_latents=[r["latent"] for r in refs if "latent" in r],
                                   cond_audio_latents=[r["audio_latent"] for r in refs if r.get("audio_latent") is not None])
        return executor(x, timestep, context, transformer_options, minimax_payload=minimax_payload, **kwargs)
    return release


# ---------------------------------------------------------------- 3. slice source by window
def _cond_latents(keyframes, refs):
    # same packed-layout order as MiniMaxH3._cond_latents: keyframes, then references
    keyframes, refs = keyframes or [], refs or []
    return {
        "cond_video_latents": [k["latent"] for k in keyframes if k.get("latent") is not None]
                              + [r["latent"] for r in refs if "latent" in r],
        "cond_audio_latents": [k["audio_latent"] for k in keyframes if k.get("audio_latent") is not None]
                              + [r["audio_latent"] for r in refs if r.get("audio_latent") is not None],
    }


def _make_source_slicer():
    # state lives in this closure (one per node run), not in a module global
    state = {}

    def on_execute_start(handler, model, x_in, conds, timestep, model_options):
        state["model"] = model
        state["retain"] = handler.cond_retain_index_list

    def on_resize_cond(cond_key, cond_value, window, x_in, device, new_cond_item):
        if cond_key != "minimax_payload":
            return None
        model = state.get("model")
        base = None
        if model is not None:
            # let the model do its own window handling first (keyframes)
            base = model.resize_cond_for_context_window(cond_key, cond_value, window, x_in, device,
                                                        retain_index_list=state.get("retain", []))
        cur = base if base is not None else cond_value
        payload = cur.cond
        idx = list(window.index_list)

        refs, changed = [], False
        for blk in payload.get("refs") or []:
            # only the source clip: a video block without audio whose length equals the target's
            if (blk.get("kind") == "video" and blk.get("latent") is not None and blk.get("audio_latent") is None
                    and not blk.get("ref_audio_t") and blk["latent"].shape[2] == window.total_frames):
                blk = dict(blk, latent=blk["latent"][:, :, idx], latent_t=len(idx))
                changed = True
            refs.append(blk)
        if not changed:
            return base  # None -> the handler's default path

        payload = {k: v for k, v in payload.items() if k != "layout"}  # the forward pass rebuilds the layout
        payload["refs"] = refs
        payload.update(_cond_latents(payload.get("keyframes"), refs))
        return cur._copy_with(payload)

    return on_execute_start, on_resize_cond


def _h3_context_windows_node():
    try:
        from comfy_extras.nodes_context_windows import MiniMaxH3ContextWindowsNode
    except ImportError as e:
        raise RuntimeError("Viggle Remake Long Video (by神棍): this ComfyUI has no 'MiniMax H3 Context Windows' "
                           "node. Update ComfyUI to 0.44.0 or newer.") from e
    return MiniMaxH3ContextWindowsNode


# ---------------------------------------------------------------- the node
class ViggleRemakeLongVideoByShenGun:
    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {
            "model": ("MODEL", {"tooltip": "The Viggle Remake model (H3 fl2va + swap/edit LoRA)."}),
            "keyframe_until": ("FLOAT", {"default": 0.9, "min": 0.0, "max": 1.0, "step": 0.01,
                                         "tooltip": "Keyframes condition every step whose sigma is at least this; below it "
                                                    "they are dropped. Same as the official Keyframe Until. Keep 0.9."}),
            "context_length": ("INT", {"default": 124, "min": 22, "max": 16384, "step": 17,
                                       "tooltip": "Window length in real frames, 17n+5. 124 = about 5.2 s at 24 fps."}),
            "context_overlap": ("INT", {"default": 39, "min": 5, "max": 16384, "step": 17,
                                        "tooltip": "Overlap between windows in real frames, 17n+5."}),
            "fuse_method": (comfy.context_windows.ContextFuseMethods.LIST_STATIC,
                            {"default": comfy.context_windows.ContextFuseMethods.PYRAMID,
                             "tooltip": "How overlapping windows are blended."}),
            "freenoise": ("BOOLEAN", {"default": True, "tooltip": "FreeNoise noise shuffling, improves window blending."}),
            "split_conds_to_windows": ("BOOLEAN", {"default": False,
                                                   "tooltip": "Split multiple conditionings (ConditionCombine) across windows. "
                                                              "Leave off for Viggle Remake."}),
            "slice_source": ("BOOLEAN", {"default": True,
                                         "tooltip": "Give every window only its own part of the source video. Off = the "
                                                    "plain official window behaviour (later windows repeat the opening)."}),
        }}

    RETURN_TYPES = ("MODEL",)
    RETURN_NAMES = ("model",)
    FUNCTION = "run"
    CATEGORY = "Viggle Remake (by神棍)"
    DESCRIPTION = ("Keyframe Until + MiniMax H3 Context Windows + Slice Source By Window in one node, for long "
                   "Viggle Remake videos. Put it between the model and the guider.")

    def run(self, model, keyframe_until, context_length, context_overlap, fuse_method, freenoise,
            split_conds_to_windows, slice_source):
        # 1. keyframe until
        m = model.clone()
        m.add_wrapper_with_key(comfy.patcher_extension.WrappersMP.DIFFUSION_MODEL, _KEY + "_keyframe_until",
                               _make_keyframe_release(keyframe_until))

        # 2. ComfyUI's own MiniMax H3 context windows
        out = _h3_context_windows_node().execute(m, context_length, context_overlap, fuse_method, freenoise,
                                                 split_conds_to_windows)
        m = out.result[0] if hasattr(out, "result") else out[0]
        handler = m.model_options.get("context_handler")
        if handler is None:
            raise RuntimeError("Viggle Remake Long Video (by神棍): the context windows were not set up.")

        # 3. slice the source clip per window
        if slice_source:
            on_start, on_resize = _make_source_slicer()
            cb = handler.callbacks
            comfy.patcher_extension.add_callback_with_key(
                comfy.context_windows.IndexListCallbacks.EXECUTE_START, _KEY, on_start, cb)
            comfy.patcher_extension.add_callback_with_key(
                comfy.context_windows.IndexListCallbacks.RESIZE_COND_ITEM, _KEY, on_resize, cb)
        return (m,)


NODE_CLASS_MAPPINGS = {"ViggleRemakeLongVideoByShenGun": ViggleRemakeLongVideoByShenGun}
NODE_DISPLAY_NAME_MAPPINGS = {"ViggleRemakeLongVideoByShenGun": "Viggle Remake Long Video by神棍"}
