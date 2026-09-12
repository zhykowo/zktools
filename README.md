# 运行依赖
- Windows 10/11
- Powershell 7
- .NET 运行时 10
- (Optional) Newbee OCR CLI

## OCR插件安装方法：
1. 下载 [newbee_ocr_cli](https://github.com/zibo-chen/newbee-ocr-cli/releases)
2. 把文件夹重命名为 newbee_ocr，放在tools目录里。脚本会自动下载模型，如果下载失败，可以手动下载三个模型到 models 目录
最终结构如下：

```
zktools/
└── tools/
    └── newbee_ocr/
        ├── nbocr.exe
        └── models/
            │── PP-OCRv6_small_det.mnn
            │── PP-OCRv6_small_rec.mnn
            └── ppocr_keys_v6_small.txt
```

# 开发&构建
- Uv
