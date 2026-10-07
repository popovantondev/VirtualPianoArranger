# Recognition model provenance

The original VPA code is MIT; model weights retain the separate terms below. No model weights are included in the Git source snapshot. VPA does not modify the listed installed ONNX files. Recognition quality remains experimental.

## HOMR 0.7.0 — AGPL

The [HOMR maintainer explicitly confirms that HOMR and its weights use AGPL](https://github.com/liebharc/homr/discussions/155). Preserve the full AGPL text with the recognition distribution.

| Installed ONNX file | SHA-256 |
| --- | --- |
| `segnet_308-3296ccd40960f90ca6ab9c035cca945675d30a0f.onnx` | `6ed36640db4ef5d223098b6d5efe4eda97c66b24a2c72faab8a018c749003a8d` |
| `encoder_pytorch_model_396-f6feedb42ff90087d898b0941a55d040fa6b2903.onnx` | `4c16df852b3789f2676b0d49f0545dab0740e4005f7b472c5252add642f5d5eb` |
| `decoder_pytorch_model_396-f6feedb42ff90087d898b0941a55d040fa6b2903.onnx` | `3e10fd5ae52d0b86792721922fcd954c283a7ed365de7446425bdabe38f3e57d` |

Upstream [ONNX release](https://github.com/liebharc/homr/releases/tag/onnx_checkpoints) and [original PyTorch checkpoint release](https://github.com/liebharc/homr/releases/tag/checkpoints). The original checkpoint ZIPs contain the exactly named `.pth` for segmentation run 308 and transformer run 396; both downloaded ZIPs passed CRC testing. Checkpoints are data, not scripts: verification did not unpickle or execute them.

Corresponding code collected for distribution:

- HOMR v0.7.0, commit `8b5dcf7d7bdd1a47911dc0c661c573b957271eab`.
- Transformer training commit `f6feedb42ff90087d898b0941a55d040fa6b2903`.
- Segmentation training commit `3296ccd40960f90ca6ab9c035cca945675d30a0f`.

The upstream tag includes architecture, training instructions, dependency lock, `training/onnx/main.py`, weight splitting, conversion, simplification and quantization code. See [the v0.7.0 export entry point](https://github.com/liebharc/homr/blob/v0.7.0/training/onnx/main.py) and [training record](https://github.com/liebharc/homr/blob/v0.7.0/Training.md). Bit-for-bit re-export is not claimed as tested. Do not confuse original checkpoints with ONNX export files or silently substitute another model version.

## RapidOCR 3.9.2 — Apache-2.0

The [RapidAI model repository card at revision v3.9.2](https://www.modelscope.cn/models/RapidAI/RapidOCR/resolve/v3.9.2/README.md) explicitly declares Apache License 2.0. Its original card is preserved with the distribution materials. The [official RapidOCR model registry](https://github.com/RapidAI/RapidOCR/blob/v3.9.2/python/rapidocr/default_models.yaml) supplies exact file URLs and expected hashes; all three installed files match them.

| Installed ONNX file | SHA-256 |
| --- | --- |
| `ch_ppocr_mobile_v2.0_cls_mobile.onnx` | `e47acedf663230f8863ff1ab0e64dd2d82b838fceb5957146dab185a89d6215c` |
| `PP-OCRv6_det_small.onnx` | `090f04abcd9d9a7498bc4ebf677e4cb9bdce1fe4197ddb7e529f1ef44e1ff94f` |
| `PP-OCRv6_rec_small.onnx` | `6f327246b50388f3c176ae304bd95767ea6dc0c9ae92153ef8cbe210b3c14884` |

Copyright (c) 2021 RapidOCR Authors. Keep the [original Apache-2.0 license](https://github.com/RapidAI/RapidOCR/blob/v3.9.2/LICENSE), applicable notices and PaddlePaddle attribution. The model conversions originate from RapidAI/RapidOCR, with original PaddlePaddle OCR models. A similarly named classifier from another repository with a different hash is not evidence for these files.

Source code: [RapidOCR v3.9.2](https://github.com/RapidAI/RapidOCR/tree/v3.9.2). Model files and original upstream source archives have not been changed by VPA. Neither Apache nor MIT here overrides HOMR's AGPL terms.
