# 齐思 · A自习室 前端 APK 打包指南（HBuilderX 云打包）
# ============================================================

## 前置条件

1. 安装 HBuilderX（https://www.dcloud.io/hbuilderx.html）
2. 注册 DCloud 账号（在 HBuilderX 中登录）
3. 项目代码已完整拉取到本地

## 步骤一：修改 manifest.json

文件路径：`uniapp/src/manifest.json`

```json
{
  "name": "A自习室",
  "appid": "",  // 留空，HBuilderX 会自动生成或手动填写
  "description": "A自习室题库系统",
  "versionName": "1.0.0",
  "versionCode": "100",
  "transformPx": false,
  "app-plus": {
    "modules": {},
    "distribute": {
      "android": {
        "permissions": [
          "<uses-permission android:name=\"android.permission.INTERNET\"/>",
          "<uses-permission android:name=\"android.permission.ACCESS_NETWORK_STATE\"/>",
          "<uses-permission android:name=\"android.permission.READ_EXTERNAL_STORAGE\"/>",
          "<uses-permission android:name=\"android.permission.WRITE_EXTERNAL_STORAGE\"/>"
        ]
      }
    }
  },
  "networkTimeout": {
    "request": 30000,
    "downloadFile": 60000,
    "uploadFile": 60000
  },
  "h5": {
    "router": {
      "mode": "hash",
      "base": "/study/"
    }
  }
}
```

## 步骤二：修改 API 请求地址（关键）

文件路径：`uniapp/src/utils/request.ts`

在文件开头添加条件编译，使 APK 内请求直接使用完整 URL：

```typescript
// #ifdef APP-PLUS
// App 环境中使用完整域名（APK 打包时生效）
const BASE_URL = 'https://qisi.chengxuelu.com/study/api/v1'
// #endif
// #ifndef APP-PLUS
// H5 环境中使用相对路径
const BASE_URL = '/api/v1'
// #endif
```

## 步骤三：在 HBuilderX 中打包

1. 打开 HBuilderX
2. 菜单：文件 → 导入 → 导入本地项目
   - 选择 `D:\yangtze\project\2026\qisi\qisi_frontend\uniapp` 目录
3. 菜单：发行 → 原生App-云打包
4. 在弹出的窗口中：
   - 选择平台：Android
   - 打包类型：公共测试证书（或选择自有证书）
   - 勾选"广告标识"（如有）
   - 点击"打包"
5. 等待打包完成（约 5-15 分钟）
6. 打包完成后会自动下载 APK 文件

## 步骤四：安装到华为平板

1. 将 APK 文件通过 USB 数据线或微信/QQ 传输到华为平板
2. 在平板上打开文件管理器，找到 APK 文件
3. 点击安装（如提示"未知来源应用"，需要在设置中允许）
4. 安装完成后，打开应用测试

## 常用 HBuilderX 快捷键

| 操作 | 快捷键 |
|------|--------|
| 运行到浏览器 | Ctrl + R |
| 发行打包 | Alt + R |
| 查找文件 | Ctrl + P |

## 注意事项

1. **条件编译**：`#ifdef APP-PLUS` 只在 APK 打包时生效，不影响 H5 开发
2. **网络权限**：确保华为平板已连接互联网
3. **HTTPS 证书**：如果服务器使用自签名证书，APK 可能无法正常请求，需要使用正式证书
4. **版本更新**：每次更新代码后，需要重新打包 APK