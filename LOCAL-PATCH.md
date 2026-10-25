# 本地补丁：macOS 27 工具链

上游 `mcncarl/jianying-headless` 已于 2026-10 下架，本仓库自此独立维护，历史已重置为单一 `main`。
本文件记录相对上游最后公开版本（`e379e07`，2026-10-15）偏离官方校验的全部改动。

## 为什么

上游把「本地编译产物的字节哈希」钉死为 `b6533eb5…`，只有维护者的工具链
（`clang-2100.1.1.101` / linker `1267`，Xcode 26.6）能复现。macOS 27 自带的
CLT 27（`clang-2100.3.34.2` / linker `27037.1`）编出的机器码不同，被硬性拒绝。
见上游 issue #2。

## 改了什么

| 文件 | 改动 |
| --- | --- |
| `tools/build_toolchain.py` | 新增 `LOCAL_TOOLCHAINS`，额外放行本机 clang/linker。**SDK 26.5 与部署目标 26.0 仍强制**，保持与评审构建最接近 |
| `tools/build_native_codec.py` | `EXPECTED_CODEC_SHA` → `0502a5d2…` |
| `bridge/SOURCE_MANIFEST.json` | `expected_codec_sha256`、`source_files['runtime_io.py']`，加 `local_deviation` 标记 |
| `bridge/runtime_io.py` | `REQUIRED_CODEC_SHA256` → `0502a5d2…` |
| `engine/headless_runtime.py` | `PINS` 两项 + `IO_MANIFEST_SHA` |
| `skills/…/headless_draft.py` | `PINS['headless_runtime.py']`、`PINS['native_export.py']` |
| `engine/jy14_headless.py` | 扩展属性校验：TCC 保护目录下内核会给新建暂存文件自动附加 `com.apple.macl`，用户态无法阻止或移除。**仅当源文件没有、目标文件被内核加上**时容忍；源文件已有的 macl 仍须逐字节保留。上游 issue #5 / PR #14 |
| `engine/windows_export.py` | FFmpeg 9 删除了 `-filter_complex_script`，改用 `-/filter_complex`（FFmpeg 7+ 支持）。上游 CI 钉在 FFmpeg 8.1.2，故未暴露 |
| `tools/repin.py` | 新增。以 `HEAD` 为基准，把改动文件的新哈希沿 pin 链自动回填，`--check` 只报告 |
| `engine/native_export.py` | MP4 容器校验：ffprobe 会把重复标签拼成 `isom;isom`，改为按 `;` 拆分后逐个校验。这是上游 bug（issue #11 / PR #13），与工具链无关 |

**没有放宽的**：剪映版本与 `libvideoeditor.dylib` 指纹校验、应用签名与 TeamID 校验、
桥接源码哈希校验、导出的帧数/分辨率/帧率/完整解码校验。

## 安全边界

源码 `jy14_codec.cpp` 仍经哈希校验，用 Apple 官方工具链本地编译，全程不下载二进制。
放弃的是「这个二进制经维护者实测验收」这一保证，不是代码来源可信度。

## 验证结果（2026-09-24，剪映 11.5.0）

- `doctor`：`status: ok`，`runtime_hashes_verified: true`
- `build` + `verify-build`：2 轨道 / 2 秒草稿，`verified`
- `export`：`encoded-and-decoded`，60/60 帧精确对齐，完整解码通过，抽帧确认画面与字幕正确
- `tests/` 8 个全过，`tools/check_package.py` 通过
- `publish`：`created`，首页索引已写入，`security_attributes_preserved: true`
- `verify`（对已登记草稿回读）：`four_mirrors_equal: true`，`source_files_unchanged: true`
- 剪映内实际打开并播放：**通过**（2026-09-27，用户在 GUI 确认）；保存后冷重开尚未验收

## 修改源码后

改完任何被 pin 的文件（`engine/`、`bridge/` 源码等）后先提交前运行：

```sh
python3 tools/repin.py --check   # 只报告哪些 pin 过期
python3 tools/repin.py           # 沿 runtime_io.py → SOURCE_MANIFEST.json → headless_runtime.py → headless_draft.py 等链回填
python3 skills/yichen-jianying-edit/scripts/headless_draft.py doctor
```

`docs/evidence/` 与 Markdown 是历史记录，不会被改写。编译产物的 codec 哈希不在此列：
重编 codec 后需手动更新 `build_native_codec.py`、`runtime_io.py` 与 `SOURCE_MANIFEST.json` 中的 `0502a5d2…`。
